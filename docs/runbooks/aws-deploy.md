---
status: runbook
---

# Runbook: deploying HerHealthGPT to AWS (one EC2 host, docker compose)

Production is **one EC2 server** running four containers — Caddy, frontend,
backend, retrieval — plus a managed RDS PostgreSQL database, all in `us-east-1`,
all described in Terraform under `infra/terraform/`. Images come from ECR; a
GitHub Actions workflow deploys by telling the host, through SSM, to run
`/opt/herhealth/deploy.sh <git-sha>`.

```
                 Route 53 (existing zone herhealthgpt.org)
                 A: herhealthgpt.org, api., www.  ->  Elastic IP
                                  |
                       +----------v-----------+  public subnet
 internet --80/443-->  |  EC2 t3.large (AL2023)|
                       |  caddy ─┬─> frontend:3000
                       |         └─> backend:8000 ──> retrieval:8001 (internal only)
                       +----------┬-----------+
                                  │ 5432 (from this security group only)
                       +----------v-----------+  private subnets
                       |  RDS PostgreSQL 16    |
                       +-----------------------+
```

> **Who does what.** `terraform apply` and every live AWS command is run **by a
> person**, from a terminal with credentials. CI never applies Terraform. An
> agent writing this repo makes no AWS calls; where a step says "run", you run it
> (in Claude Code, prefix with `!`).

## Deliberate trade-offs — read these before demoing

| Trade-off | What it means | Why |
|---|---|---|
| **Single server** | If the host fails, the site is down until EC2 auto-recovers it (minutes, hardware faults only) or you recover it by hand. No second node, no autoscaling. | About a third cheaper than the container-service design that was considered (about $93 against about $140 a month). A student-project load does not need redundancy. |
| **Single-AZ RDS** | An AZ outage means downtime until restore from backup. | Multi-AZ doubles the database bill. |
| **7-day backups** | Point-in-time recovery for a week. | Cost. |
| **No staging environment** | Every deploy goes to the live site. The automatic rollback is the only safety net, and it restores images and config files, **not** the database schema (see [Rollback](#8-rollback)). | One environment is all the budget covers. |
| **No WAF** | Caddy and the app are directly on the internet. | Cost. Rate limits in the app (resend limits, wrong-code lockout) are the only abuse control. |
| **Control of `main` is control of the server** | The deploy role uploads `deploy.sh`, `compose.prod.yml` and the Caddyfile to `deploy/<sha>/`, and the host runs them **as root**. The custom SSM document restricts the **command line** (one validated `Sha` parameter), **not the content** that runs. So anyone who can push to `main`, or merge into it, can run anything as root on the host, read the database credentials in `/run/herhealth`, and read every user's data. | Deploying on a push needs a path from the repository to the server, and this is its price. The mitigations are procedural, not technical: required reviews and status checks on `main`, no direct pushes, no admin bypass, and few people with write access. |
| **NHS text excluded from the deployed index** | Production retrieval cannot return NHS passages or the 53 evidence statements backed by NHS rows — see [the NHS decision](#the-nhs-decision). The index is built with `--exclude-quote-only`. | Licence: NHS content is `citable_only`. |
| **Base model only** | No fine-tuned adapter in production — see [Model](#model-base-only-in-production). | The adapter is not cleared to make triage decisions. |

## 0. What already exists (verified read-only, 2026-10-06)

Nothing below is created or changed by Terraform.

| Item | State |
|---|---|
| AWS account | `508859666073`, signed in as IAM user `admin` (not root) |
| Route 53 zone | `Z07921208OVVINWPK4MY`, public, 8 records: NS, SOA, `_dmarc` TXT, three DKIM CNAMEs, `bounce.` MX and SPF TXT. **No A, MX or TXT at the apex, none for `api` or `www`.** |
| Name servers | `ns-1322.awsdns-37.org`, `ns-1758.awsdns-27.co.uk`, `ns-508.awsdns-63.com`, `ns-991.awsdns-59.net` |
| SES | Domain identity `herhealthgpt.org` **verified**, Easy DKIM SUCCESS (the three tokens in [ses-production-access.md](ses-production-access.md)), MAIL FROM `bounce.herhealthgpt.org` SUCCESS. **Production access granted** (case `178653944300665`), 50,000/24h, 14/s, enforcement `HEALTHY`. Account suppression list on for bounces and complaints. |

Because SES is fully set up, `ses.tf` only grants the instance role
`ses:SendEmail` on the identity ARN (conditioned on `ses:FromAddress =
no-reply@herhealthgpt.org`). The procedure that created SES is in
[ses-production-access.md](ses-production-access.md); this runbook does not
repeat it. If production access were ever lost (sandbox), only verified
recipients could receive mail — that runbook is where to get it back.

**Known gaps in what SES was told** (recorded here because the account's
approved use-case text says otherwise): DMARC is `p=none` (not enforced), and
bounce/complaint notifications via SNS are **not built** — the account-level
suppression list covers the effect, but nothing in the app consumes the events.

## 1. Account and IAM bootstrap

Terraform and the one-off commands run as the IAM user `admin` (never root).

```bash
aws configure                        # or: aws login
aws sts get-caller-identity          # expect Account 508859666073, user/admin
terraform version                    # >= 1.10 (native S3 locking)
```

You also need the [Session Manager
plugin](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html)
locally to open a shell on the host (§13).

**Before the first apply, check for an existing GitHub OIDC provider.** An AWS
account can hold only one OIDC provider per URL, and creating a second one fails
the apply partway through. Run this first (read-only):

```bash
aws iam list-open-id-connect-providers
```

- If it lists an ARN ending in `oidc-provider/token.actions.githubusercontent.com`,
  set `create_github_oidc_provider = false` in `terraform.tfvars`, so Terraform
  reads the existing provider instead of creating one.
- If the list is empty, leave the default (`true`).

The variable stays a variable because the answer depends on the account, not on
this repository.

## 2. State bootstrap (once)

The prod stack keeps its state in S3 with native locking (`use_lockfile`; no
DynamoDB). This stack creates only that bucket (versioned, SSE-S3, public access
blocked) and keeps its own state **locally** — the bucket cannot hold the state
of the stack that creates it.

```bash
cd infra/terraform/bootstrap
terraform init
terraform apply              # review the plan: one bucket and its settings
```

Bucket name: `herhealthgpt-tfstate-508859666073`, matching
`infra/terraform/prod/versions.tf`. The local `terraform.tfstate` is gitignored;
losing it is harmless (`terraform import aws_s3_bucket.state <bucket>`), and the
bucket has `prevent_destroy`.

## 3. Plan and apply the prod stack

Copy `infra/terraform/prod/terraform.tfvars.example` to `terraform.tfvars`
(gitignored: every `*.tfvars` is) — only two values have no default:

```hcl
alert_email    = "you@example.org"   # alarms, budget alerts, Let's Encrypt notices
compose_sha256 = "<64 hex>"          # see below
```

Decide two optional switches before the first apply: `create_github_oidc_provider`
(see §1: run `aws iam list-open-id-connect-providers` first) and `create_plan_role`
(default `false`; see §5, "The plan role").

`compose_sha256` is the checksum of the Docker Compose plugin binary the host
downloads at first boot (`compose_version` in `variables.tf`; Amazon Linux 2023
does not package the plugin). It has no default on purpose: the binary runs as
root, so a person looks the checksum up on the release page of that exact tag.
**Verify the tag exists first.**

```bash
cd infra/terraform/prod
terraform init
terraform plan -out=tfplan   # READ it all. Nothing here should surprise you.
terraform apply tfplan
```

Commit the generated `infra/terraform/prod/.terraform.lock.hcl` (provider pins).

The plan **fails by design** if the Route 53 zone found for `herhealthgpt.org`
does not carry exactly the four name servers above — see [the mismatch
failure](#route-53-name-server-mismatch).

First apply creates, among others: VPC and subnets, the EC2 host and its Elastic
IP, RDS, three ECR repositories, the artifacts bucket, empty Secrets Manager
entries, log groups, alarms, the budget, the GitHub OIDC roles, and the three
Route 53 A records. It takes about 10–15 minutes (RDS dominates).

Afterwards:

1. **Confirm the SNS subscription.** AWS emails `alert_email` a confirmation
   link; alarm mail goes nowhere until it is clicked. (The AWS Budget alert needs
   no confirmation: it simply starts arriving.)
2. The host is up but **runs no containers yet** — nothing crash-loops, because
   there is nothing to run until the first image is pushed (§7). Confirm
   first boot finished: open a shell (§13) and run `test -f
   /opt/herhealth/.bootstrap-ok && echo bootstrap ok`. If it is missing,
   cloud-init stopped partway: read `/var/log/herhealth-bootstrap.log`, and see
   [First apply: what was not tested locally](#first-apply-what-was-not-tested-locally).
3. Record the outputs: `terraform output`.

### Route 53 name server mismatch

Symptom: `terraform plan` stops with *"Hosted zone herhealthgpt.org has name
servers …, expected …"*.

Meaning: a hosted zone with that name exists but is not the one the domain is
delegated to (for example a second zone created by hand). Records written to it
would never be reachable. Terraform refuses to proceed.

Fix, in order: (1) `aws route53 list-hosted-zones-by-name --dns-name
herhealthgpt.org` — expect **one** zone, `Z07921208OVVINWPK4MY`; (2) if there is
a second, empty zone, delete it; (3) compare with the registered domain's name
servers (`aws route53domains get-domain-detail --domain-name herhealthgpt.org
--region us-east-1`). Only if the registrar's set legitimately changed, update
`expected_name_servers` in `variables.tf` in a reviewed commit. **Never** loosen
the check to get a plan through.

## 4. Filling secrets

Terraform creates these **empty**; no value ever passes through Terraform or
its state. Fill each once:

```bash
aws secretsmanager put-secret-value --secret-id herhealth/prod/openrouter-api-key \
  --secret-string 'sk-or-...'
aws secretsmanager put-secret-value --secret-id herhealth/prod/session-secret \
  --secret-string "$(openssl rand -hex 32)"
aws secretsmanager put-secret-value --secret-id herhealth/prod/google-client-id \
  --secret-string '<client id>.apps.googleusercontent.com'
```

There is no Lobot token and no `HERHEALTH_VLLM_*` secret. The database password
is the RDS-managed secret; you never handle it.

The host's `refresh-secrets.sh` turns these into `/run/herhealth/backend.env` on
**tmpfs** at deploy time. They are never baked into an image and never written to
disk.

### Database password rotation

RDS rotates its managed master password (every 7 days by default) and the old
password stops working immediately. Containers read their environment only when
they are *created*, so a running backend keeps its open connections but cannot
open new ones after a rotation.

The simplest safe option, and what is built: a systemd timer that runs every
**15 minutes** (`herhealth-refresh-secrets.timer`) re-reads the secret, and if the
database URL changed, recreates **only the backend** with the new one (a few
seconds). Every deploy also re-reads it. Worst case, the backend can fail to open
*new* connections for up to 15 minutes after a rotation. Check with
`systemctl list-timers herhealth-refresh-secrets.timer` and
`journalctl -u herhealth-refresh-secrets`. `/health` pings the database, so a
rotation that is not picked up shows as an unhealthy backend.

## 5. GitHub: variables and the deploy role

In the repository's **Settings → Secrets and variables → Actions → Variables**
(none of these is a secret):

| Variable | Value |
|---|---|
| `AWS_DEPLOY_ROLE_ARN` | `terraform output deploy_role_arn` |
| `AWS_PLAN_ROLE_ARN` | `terraform output plan_role_arn` — **only if** `create_plan_role = true` (§5, "The plan role") |
| `EC2_INSTANCE_ID` | `terraform output instance_id` |
| `ARTIFACTS_BUCKET` | `terraform output artifacts_bucket` |
| `NEXT_PUBLIC_GOOGLE_CLIENT_ID` | the Google OAuth client id |
| `RETRIEVAL_INDEX_VERSION` | printed by `publish-index.sh` (§6) |
| `BGE_M3_REVISION` | the 40-hex Hugging Face commit (§6) |
| `TF_VAR_ALERT_EMAIL`, `TF_VAR_COMPOSE_SHA256` | the same two `terraform.tfvars` values, for PR plans — **only if** the plan job is enabled |

The **deploy role** is trusted only for pushes to `main` of
`HerHealthGPT/herhealthgpt` (the `sub` claim is case-sensitive — the casing comes
from `git remote -v`). It can push to the three ECR repositories, write the
`deploy/` prefix, read the `index/` prefix, and run **one custom SSM document,
`herhealth-deploy`**, on **this one instance** (`ssm.tf`). The document runs a
fixed command, `/opt/herhealth/deploy.sh {{ Sha }}`, and its single parameter is
validated by SSM against `^[0-9a-f]{7,64}$` before the command is built.

That restricts the **command line**: the role cannot hand SSM an arbitrary command
string (it has no access to `AWS-RunShellScript`), so no shell metacharacters can
reach it. It does **not** restrict **what runs**. `deploy.sh` replaces itself from,
and then executes, as root, the files **this same role uploads** to
`deploy/<sha>/`. **Control of `main` is control of the server**: the first row of
the trade-offs table, and the table below, say the same thing. Protect `main` with
required reviews and the `backend` / `data` test checks, no direct pushes and no
admin bypass, because `deploy` itself does not run tests.

### The plan role (optional, off by default)

The separate **plan role** (pull requests, read-only plus the state lock file)
exists because pull-request OIDC tokens carry a different `sub` than `main`. It
is created only if `create_plan_role = true` in `terraform.tfvars`; the default
is **`false`**. With it off there is no role, no `AWS_PLAN_ROLE_ARN`, and the
`plan` job in `terraform.yml` is **skipped** (shown as neutral, not red). `fmt`
and `validate` still run on every pull request, so the only thing lost is the plan
comment on the PR; run `terraform plan` locally instead.

**What enabling it costs.** The role attaches AWS's `ReadOnlyAccess` policy, which
is not limited to this stack: it reads the configuration **and the contents** of
the whole account, including **S3 objects in every bucket** (the artifacts and
state buckets among them) and **CloudWatch Logs events** (`/herhealth/prod/*`).
Anyone who can open a pull request in this repository can change a workflow to run
as this role and read them. That matters if the logs can contain user text, and
they can; see [What the logs can contain](#what-the-logs-can-contain). To enable:
set `create_plan_role = true`, `terraform apply`, then set `AWS_PLAN_ROLE_ARN` and
the two `TF_VAR_*` repository variables.

### What the logs can contain

Checked by reading every logging call in `services/backend` and `services/model`
(and the retrieval library they use). **No logging call takes a message body,
request body or conversation history**, and uvicorn's access log records method,
path and status, not bodies. But user text and personal data can still reach the
container logs, and therefore CloudWatch:

| Where | What can appear |
|---|---|
| `email_sender.py` console sender | The recipient's email **and the verification code**. Used when `HERHEALTH_EMAIL_SENDER` is `console`, which is the code's **default if the variable is unset**; production sets `ses` in `compose.prod.yml`. |
| `email_verification.py`, `password_reset.py` | The recipient's **email address**, with a traceback, when sending a code fails. |
| `routes.py` (`dropped answer` warning) | The feature the user was asked about and the **answers recorded this turn** (closed-vocabulary answers to health questions), when the model's decision ignored them. |
| `routes.py` / `clients.py` retry warnings | The text of a validation or value error, which can quote the **reasoning model's output** (and so words from the conversation). |
| `logger.exception(...)` on database errors | The SQLAlchemy engine does **not** set `hide_parameters`, so a database error's message can include the **bound SQL parameters**: message text, email addresses, password hashes. |
| Retrieval service, web fallback | Not CloudWatch: when the index has nothing usable for a turn, it appends the **retrieval query** (composed from the conversation) to `build/web_fallback_review_queue.jsonl` **inside the container**, where it is lost at the next deploy. Errors writing it are swallowed. |

Recommended follow-ups, **not made here** because this change does not touch
application code: `create_async_engine(..., hide_parameters=True)` in `db.py`;
stop logging `observed` answers and exception text at WARNING; and decide whether
the fallback's review queue should exist in production at all.

### Who can write what the host executes

`deploy.sh`, `compose.prod.yml` and the Caddyfile are downloaded from
`s3://<bucket>/deploy/<sha>/` and run **as root** on the host, so write access to
that prefix is effectively root on the server. Verified in the Terraform:

| Principal | `deploy/*` | Where in the code |
|---|---|---|
| GitHub **deploy role** (pushes to `main` only) | **write** (`s3:PutObject`) | `iam_oidc.tf`, statement `UploadDeployFiles`; trust policy pinned to `ref:refs/heads/main` |
| GitHub **plan role** (pull requests; only if `create_plan_role = true`) | **no write** to this bucket: `ReadOnlyAccess` (get/list only) plus `Put/DeleteObject` on the *state bucket's* lock file only | `iam_oidc.tf`, `plan_readonly` and `plan_lock` |
| **Instance role** | read-only (`s3:GetObject`); it can write only `caddy-backup/*` | `iam_instance.tf`, statements `ReadDeployFiles` and `CaddyBackupObjects` |
| `admin` IAM user | everything | outside Terraform |

The bucket is **versioned** (`s3.tf`, `aws_s3_bucket_versioning`; deploy files
expire after 30 days, noncurrent versions after 7), so an overwritten object can
be recovered. Not enforced: a push to `main` could rewrite an *existing*
`deploy/<sha>/` prefix, and `deploy.sh` does not verify file checksums. The
protection is who can push to `main`: require reviews on it.

Add `https://herhealthgpt.org` to Google's OAuth client — see
[Google sign-in in production](#google-sign-in-in-production).

## 6. The retrieval index

The retrieval image bakes `build/index/` (vectors, passages, manifest). That
directory is generated and gitignored, so production gets it from the artifacts
bucket: published **once per version**, read by CI, never edited.

### The NHS decision

`run_index` embeds NHS passages on purpose (we may *read and quote* them, which
authoring needs), flagging each `may_be_ingested=False`;
`services/model/src/herhealth_model/app.py` filters them at query time, **before** top-k ranking. But the index *files*
still contain the NHS text. Decision: **no NHS text may enter the S3 bucket or
any container image.** So the deployed index is to be built with a flag
(`--exclude-quote-only`) that drops every `may_be_ingested=False` passage before
embedding, and `scripts/publish-index.sh` refuses to upload an index that has
any.

> **Status: implemented** on the `index` command (2026-10-09), with tests in
> `services/data/tests/test_cli.py`. Without the flag the index still holds NHS
> text, and `publish-index.sh` refuses it.

What it changes, and what it does not:

- **Retrieval results are identical to today's served behaviour.** The runtime
  filter already ranked only ingestable passages, so removing the rest at build
  time returns the same top-k (the only difference would be an exact score tie).
- **It does shrink the evidence-statement pool.** Each evidence statement embeds
  its `source_quote` verbatim, so every NHS-backed row is dropped: **53 of the
  146 rows** in `knowledge/evidence.csv` as of this writing. `adenomyosis` (NHS
  only) has no evidence statement in production, and neither do the features
  `abnormal_discharge`, `bloating_or_digestive_symptoms` and
  `low_mood_or_anxiety` (NHS-only rows). That was already true at query time;
  production simply cannot return them. Where NHS is the *only* source, a missing
  statement is the correct representation of a source we may not serve.
- **The 2026-09-02 evaluation numbers refer to a different, unfiltered index**
  (4,454 passages, NHS included in the files). They are not the numbers for this
  deployed index. Quote any retrieval figure with the index it came from.

### Building the index (needs a network step — ask first)

There is **no `make index` target** in the Makefile (the Dockerfile, ADR 0011 and
other docs mention one; it was never added). The command that exists:

```bash
make fetch && make clean          # NETWORK: fetches source pages. Ask first.
uv run --extra retrieval python -m herhealth_data.cli index \
    --exclude-quote-only --index-dir build/index-deploy
```

Inputs: `build/clean/*.json` (from `make clean`) and `knowledge/`. Model:
`BAAI/bge-m3` (sentence-transformers), L2-normalised, no prefixes, batch 128,
float32, 1024 dimensions, brute-force cosine search (no FAISS, no reranker — ADR
0010). `--exclude-quote-only` is required for production (see the status note
above).

The index must be built with **the same bge-m3 revision the image bakes**. The
CLI cannot take a revision, so pin the weights through the Hugging Face cache
(the Dockerfile does the same for the image):

```bash
python -c "import os, pathlib; from huggingface_hub import snapshot_download; \
rev = '<40-hex sha>'; snap = pathlib.Path(snapshot_download('BAAI/bge-m3', revision=rev, ignore_patterns=['onnx/*', 'imgs/*', '*.jpg', '*.png'])); \
refs = snap.parents[1] / 'refs'; refs.mkdir(exist_ok=True); (refs / 'main').write_text(rev)"
HF_HUB_OFFLINE=1 uv run --extra retrieval python -m herhealth_data.cli index \
    --exclude-quote-only --index-dir build/index-deploy
```

> **Open: a built copy of the 2026-09-02 index.** If the team has one, a filtered
> index can be *derived* from it with no re-embedding and no network: drop the
> rows where `may_be_ingested` is false from `passages.jsonl` and the matching
> rows of `vectors.npy` (line *i* ↔ row *i*) and rewrite the manifest count. But
> it would lack the evidence rows added since (146 now vs 140 then), and its
> bge-m3 revision is unknown. A rebuild is the way to a known-good pin.

### One-time upload

```bash
scripts/publish-index.sh --index-dir build/index-deploy \
    --bge-m3-revision <40-hex sha> --dry-run     # every check, no AWS
scripts/publish-index.sh --index-dir build/index-deploy \
    --bge-m3-revision <40-hex sha> --bucket "$(terraform -chdir=infra/terraform/prod output -raw artifacts_bucket)"
```

It refuses if `manifest.json` `model_name` is not `BAAI/bge-m3` (the hashing
stand-in must never ship), if any passage is `may_be_ingested=false` or from the
`nhs` source, if the three files disagree on the passage count, or if that
version already exists. The version is a content hash. It writes
`s3://<bucket>/index/<version>/` (SSE-S3) including `build-info.json`
(`bge_m3_revision`, passage count, publish time). Then set the repository
variables `RETRIEVAL_INDEX_VERSION` and `BGE_M3_REVISION`.

CI re-verifies all of this before building, **fails if the index's recorded
revision differs from `BGE_M3_REVISION`**, and records both as image labels
(`org.herhealthgpt.index-version`, `org.herhealthgpt.bge-m3-revision`) —
`docker inspect` tells you what a running image was built from.

**Later alternative (not built):** put the vectors in the RDS instance with
pgvector. It would remove the index-publish step and let the index change
without an image rebuild, at the cost of a retrieval rewrite (`PassageIndex` is
a numpy matrix today) and a re-evaluation. bge-m3 still has to run somewhere
either way — pgvector stores vectors, it does not embed queries.

## 7. First deploy

Before any image exists the host runs nothing, and that is correct. Once §3–§6
are done:

1. **Check DNS resolves to the Elastic IP, for all three names, before you start.**
   Let's Encrypt validates by reaching the server over HTTP on port 80 at that
   name; if DNS still points elsewhere the validation fails.
   ```bash
   EIP=$(terraform -chdir=infra/terraform/prod output -raw elastic_ip)
   for h in herhealthgpt.org api.herhealthgpt.org www.herhealthgpt.org; do
     echo "$h -> $(dig +short "$h" | tr '\n' ' ')  (expect $EIP)"
   done
   ```
   If you restored certificates (§11), also confirm `caddy-data.sh restore` ran.
2. Run the workflow: **Actions → deploy → Run workflow** (or merge to `main`).
3. It builds the three images tagged with the commit SHA, pushes them, uploads
   `compose.prod.yml` / `Caddyfile` / the scripts to `s3://…/deploy/<sha>/`, then
   runs `deploy.sh <sha>` through SSM and prints its output.

`deploy.sh` on the first run: logs in to ECR, pulls (retrieval is several GB, so
this is slow), runs `alembic upgrade head` in a one-off container, starts the
stack, waits for the image healthchecks, then checks
`https://api.herhealthgpt.org/health` and `https://herhealthgpt.org/` **through
Caddy**. The first request makes Caddy obtain its Let's Encrypt certificates
(three names), which is why the check retries for about three minutes. There is
no previous tag on a first deploy, so a failure leaves the stack in place for you
to inspect rather than rolling back to nothing.

Expect the **first** deploy to take 15–25 minutes.

**If the first deploy fails, re-running `deploy.sh` is safe**: every step is
idempotent, and with no previous release there is nothing to roll back to, so the
stack is left up for you to inspect. **But do not loop on it.** Let's Encrypt
limits *failed validations* (about five per hostname per hour), and a retry loop
against a DNS or port-80 problem will exhaust that and lock issuance out for the
hour. Read the failure, fix the cause (DNS, security group, a Caddyfile error),
then re-run once. Caddy also retries issuance on its own with backoff, so the
health check waiting about 3 minutes is not itself a loop.

## 8. Rollback

**Normal path: `git revert` on `main`.** The workflow rebuilds and redeploys the
reverted code like any other change.

**Automatic path:** if a deploy's health check fails, `deploy.sh` rolls the host
back to the previous tag by itself (this replaces a load balancer's deployment
circuit breaker) and exits non-zero so the workflow fails. The workflow output
says whether the rollback itself is healthy.

> **Limit.** Rollback restores the previous *images and the previous
> `compose.prod.yml` / Caddyfile* (kept in `/opt/herhealth/previous/`). It does **not** revert the
> database: `alembic upgrade head` already ran. Write migrations as
> expand/contract — add columns and tables in one release, remove them in a later
> one — so that the previous release still runs against the new schema. A
> destructive migration followed by a rollback means old code on a schema it does
> not understand.

If the whole host is in a bad state, see [Troubleshooting](#14-troubleshooting).

## 9. Deploy anatomy and disk space

`deploy.sh` is idempotent per SHA and takes a lock, so two runs cannot overlap.
Before pulling it always removes every image except the running release (so at
most the running and the new release are on disk during a pull), then requires
15 GB free. After a successful deploy it keeps the new and the previous release
for rollback. The root volume is **60 GB** (`root_volume_gb`).

**Image sizes: estimates, not measurements** (nothing has been built yet; replace
these with `docker images` after the first deploy):

| Image | Uncompressed on disk | Compressed in ECR | Why |
|---|---|---|---|
| `herhealth-backend` | about 0.5-0.7 GB | about 0.2-0.3 GB | python slim + FastAPI, SQLAlchemy, psycopg, boto3, argon2 |
| `herhealth-frontend` | about 0.35-0.5 GB | about 0.15 GB | node slim + the Next.js standalone output |
| `herhealth-retrieval` | **about 8-10 GB** | **about 4-5 GB** | torch **with CUDA libraries** (about 5-6 GB) + bge-m3 weights (about 2.3 GB) + Python deps |

The retrieval figure is dominated by something the Dockerfile's "CPU only"
comment does not deliver: `uv.lock` resolves `torch 2.13.0` from PyPI, whose Linux
wheel depends on the CUDA 13 stack (`cuda-toolkit`, `nvidia-cudnn`, `nvidia-nccl`,
and more). This host has no GPU, so those gigabytes are dead weight in every
image, in ECR, on the volume and in every pull. Switching the retrieval image to a
CPU-only torch wheel would cut it to roughly 3.5-4 GB; that is a change to
`pyproject.toml` / `uv.lock` (a shared file and a network re-lock), so it is
**not done here**. It is the first thing to try if pulls or disk hurt.

One release is therefore about 9-11 GB; the running plus the new release about
20 GB at the peak of a deploy, plus the OS, swap and logs.

```bash
df -h /                                   # root volume
docker system df                          # what Docker is holding
docker images --format '{{.Repository}}:{{.Tag}}  {{.Size}}'
```

A CloudWatch alarm fires at 80% disk (CloudWatch agent, namespace `HerHealth/EC2`)
and at 90% memory. To free space by hand, keeping the running release and the
previous one:

```bash
sudo docker image prune -f               # dangling layers
cat /opt/herhealth/release.env           # TAG = running release
# remove older tagged images explicitly:  sudo docker image rm <repo>:<old-tag>
```

If a deploy aborts with "GB free after pruning", the volume is too small:
raise `root_volume_gb` and apply (EBS grows online; then `sudo growpart` and
`sudo xfs_growfs /`).

## 10. Stop between sessions

To stop paying for compute between demos/working sessions:

```bash
INSTANCE=$(terraform -chdir=infra/terraform/prod output -raw instance_id)
aws ec2 stop-instances --instance-ids "$INSTANCE"
aws rds stop-db-instance --db-instance-identifier herhealth-prod
```

**Still billed while stopped:** the EBS volume, the **Elastic IP** (a public IPv4
address is billed whether or not it is attached), RDS storage and backups,
Secrets Manager, ECR and S3 storage — roughly $18/month in all.

> **RDS restarts itself after 7 days.** AWS starts a stopped instance
> automatically after 7 days, and compute billing resumes. Put a reminder in your
> calendar, or stop it again.

> **A deploy needs RDS running.** `/health` pings the database, so a stopped RDS
> makes it return 503, which a deploy reads as a bad release and rolls back.
> `deploy.sh` therefore checks that it can reach the database *before* changing
> anything and stops with "Is RDS stopped?". Start RDS, wait for `available`, and
> re-run. Do not trigger a deploy while RDS is stopped.

To resume: `aws rds start-db-instance …` and wait for `available`, then
`aws ec2 start-instances …`. Containers have `restart: unless-stopped` and come
back on their own; Caddy's certificates are on the persistent volume. The
CloudWatch `StatusCheckFailed_System` alarm may notify while the instance is
stopped; ignore it.

## 11. Destroy and recreate

**Back up first**, in this order:

1. **RDS final snapshot.** `terraform destroy` takes one automatically
   (`herhealth-prod-final`, from `db_final_snapshot_identifier`), but only once
   deletion protection is off (step 3). A snapshot with that name from an earlier
   destroy makes the next destroy fail: delete or rename it first
   (`aws rds describe-db-snapshots --db-snapshot-identifier herhealth-prod-final`).
2. **Save Caddy's certificates:** on the host,
   `sudo /opt/herhealth/caddy-data.sh backup` (writes to the artifacts bucket).
   Let's Encrypt allows only **5 duplicate certificates per week** for the same
   set of names. A recreated server asks for new ones, so several
   destroy/recreate cycles in a week leave the site with no valid certificate
   until the limit resets. After recreating, `sudo /opt/herhealth/caddy-data.sh
   restore` **before the first deploy** and no new certificate is requested.
   When *rehearsing*, put `ACME_CA=https://acme-staging-v02.api.letsencrypt.org/directory`
   in `/opt/herhealth/local.env` first (staging certificates are not trusted by
   browsers, but have far higher limits).
3. Disable protection: set `db_deletion_protection = false` in `terraform.tfvars`,
   `terraform apply` (changes only that flag), then `terraform destroy`.

The artifacts bucket, ECR repositories (immutable tags) and state bucket are not
emptied automatically; remove them by hand if you really want them gone.
The state bucket has `prevent_destroy`.

To replace **only the server** (new bootstrap script, new instance type with a
different AMI), `terraform apply -replace=aws_instance.app` — `user_data` and the
AMI are deliberately ignored in plans so they never replace the host by
accident. Do the Caddy backup first.

## 12. Model: Base only in production

Production runs `HERHEALTH_TRIAGE_MODE=openrouter` with the **Base** model
(Qwen3.5-9B via OpenRouter) and `HERHEALTH_MODEL_SELECTOR=off`. No
`HERHEALTH_VLLM_URL`, `HERHEALTH_VLLM_MODEL` or `HERHEALTH_VLLM_API_KEY` exists in
the compose file or the secrets. `default_model_id` is not touched here.

Why: the fine-tuned adapter is phrasing-trained, has no clarifying-question turns
in its training data, and is not cleared to own triage decisions until the
multi-turn retrain is reviewed (CLAUDE.md, "The fine-tuned model"). Nothing about
that has changed. The fine-tuned model stays campus/dev-only —
[uni-server-vllm.md](uni-server-vllm.md).

> **Enabling Fine-tuned in production requires an explicit written
> team/supervisor decision and an ADR first.** The model selector's dev-only
> scoping is recorded in ADR 0016, per the team; **that file is not in this
> checkout** (the newest ADR here is 0015), so it lives on another branch — find
> it before relying on this paragraph's wording.

## 13. Working on the host

No SSH, no key pair. Everything goes through SSM.

```bash
aws ssm start-session --target "$(terraform -chdir=infra/terraform/prod output -raw instance_id)"
sudo -i
cd /opt/herhealth
```

| Want | Command |
|---|---|
| What is running | `docker compose -p herhealth --env-file release.env -f compose.prod.yml ps` |
| Running release | `cat /opt/herhealth/release.env` (`TAG=`) |
| Live config files | `/opt/herhealth/compose.prod.yml`, `/opt/herhealth/caddy/Caddyfile` (previous release's copies in `previous/`) |
| Logs, live | `docker logs -f herhealth-backend-1` (also `-frontend-1`, `-retrieval-1`, `-caddy-1`) |
| Logs, history | CloudWatch Logs: `/herhealth/prod/{caddy,frontend,backend,retrieval}` (retention 30 days) |
| First-boot log | `/var/log/herhealth-bootstrap.log` |
| Deploy history | the GitHub Actions run (it prints `deploy.sh`'s output), and Systems Manager → Run Command → Command history in the console |
| Image provenance | `docker inspect <image> --format '{{json .Config.Labels}}'` (index version, bge-m3 revision) |
| Memory / disk | `free -h`, `df -h /` |

**Do not edit files on the server to change behaviour.** Change the repo and
deploy; the next deploy overwrites `compose.prod.yml` and the `Caddyfile`. The
shell is for reading and diagnosing. The one hand-edited file that is meant to
exist is `/opt/herhealth/local.env` (e.g. `ACME_CA`).

Security updates install automatically (`dnf-automatic`, security errata only).
Kernel updates need a reboot to take effect and do **not** reboot by themselves:
`sudo reboot` in a quiet moment about monthly. Containers restart on their own.

## Google sign-in in production

Add `https://herhealthgpt.org` to the OAuth client's **Authorized JavaScript
origins** and **Authorized redirect URIs** — see
[google-oauth-client.md](google-oauth-client.md) §3. The Client ID is needed in
**two** places: as the repository variable `NEXT_PUBLIC_GOOGLE_CLIENT_ID` (baked
into the frontend bundle at build time) and as the secret
`herhealth/prod/google-client-id` (the backend verifies the token's audience
against it). The client *secret* is never used and never stored.

## How the frontend reaches the backend

All API calls are made **by the browser**, directly to `https://api.herhealthgpt.org`
(`NEXT_PUBLIC_API_URL`, inlined into the bundle at build time — which is why it is
a build argument in `deploy.yml`, not a runtime variable). The two hosts are
same-site, so the SameSite=Lax auth cookies are sent with `credentials:
"include"`, and the backend allows exactly `https://herhealthgpt.org` through
`HERHEALTH_CORS_ORIGINS`. The `/api` rewrite in `next.config.ts` (to
`BACKEND_URL`, baked in as `http://backend:8000`) is never used in production.

## First apply: what was not tested locally

Everything below was reasoned about, not run, because it needs a real Amazon
Linux 2023 instance, the AWS control plane or the public internet. Check each on
the first apply, in this order:

| Risk | How to check |
|---|---|
| **cloud-init / package names on AL2023** (`docker`, `jq`, `amazon-cloudwatch-agent`, `dnf-automatic`; the Compose plugin download and checksum) | `test -f /opt/herhealth/.bootstrap-ok`; `docker compose version`; `rpm -q docker jq amazon-cloudwatch-agent dnf-automatic`; `systemctl is-enabled dnf-automatic.timer`; `grep -E '^(upgrade_type|apply_updates)' /etc/dnf/automatic.conf`. The bootstrap script exits loudly (and writes no marker) if any of these fail. |
| **The SSM document is delivered and runs** | `aws ssm describe-document --name herhealth-deploy`; trigger the workflow; or `aws ssm send-command --document-name herhealth-deploy --parameters Sha=<sha> --instance-ids <id>` once. Then try a bad value (`--parameters 'Sha=abc; id'`): it must be rejected by SSM before anything runs. |
| **`/run` is tmpfs and the env file is mode 600** | on the host: `findmnt -no FSTYPE -T /run` (expect `tmpfs`) and `stat -c '%a %U' /run/herhealth/backend.env` (expect `600 root`). `refresh-secrets.sh` refuses to write if `/run` is not tmpfs. |
| **Caddy certificate timing vs the health check** | the first deploy waits about 3 minutes for HTTPS to answer. If the log says the health check failed but `https://herhealthgpt.org` works a minute later, issuance was slow, not broken: re-run **once** (DNS correct first; see §7). |
| **`ses:FromAddress` condition** | send a real verification email through the site. `AccessDenied` on `ses:SendEmail` means the condition did not match: remove it from `ses.tf`, apply, and say so here. |
| **The alembic path inside the image** | `deploy.sh` runs `alembic upgrade head` with working directory `/app/services/backend`. If the migration step fails with "No config file" or "Can't locate revision", check `docker run --rm --entrypoint sh <backend image> -c 'ls /app/services/backend/alembic.ini /app/services/backend/migrations'`. |
| **Image builds** | neither Dockerfile has been built. The first CI run is the first build. |
| **ECR / S3 / OIDC permissions** | the first workflow run: a `AccessDenied` names the missing action. |

## 14. Troubleshooting

| Symptom | Likely cause | What to do |
|---|---|---|
| `terraform plan`: "Hosted zone … has name servers" | Wrong or duplicate hosted zone | [Name server mismatch](#route-53-name-server-mismatch) |
| `terraform plan`: `compose_sha256` invalid | Not 64 lowercase hex | Look it up on the Compose release page for `compose_version` |
| `terraform apply`: A record already exists | Something already points at that name | Do not overwrite; find out what, decide, then delete or import deliberately |
| Workflow: "repository variable … is not set" | §5 not finished | Set the variable named in the error |
| Workflow: "built with bge-m3 revision X, but BGE_M3_REVISION is Y" | Index and image pinned to different weights | Set `BGE_M3_REVISION` to the index's revision, or rebuild and republish the index |
| Workflow: quote-only passage found in the index | Wrong index published | Rebuild with `--exclude-quote-only`, republish, update `RETRIEVAL_INDEX_VERSION` |
| Workflow: cannot assume role | Not on `main`, or repo casing | The role trusts only `repo:HerHealthGPT/herhealthgpt:ref:refs/heads/main` |
| Workflow: cannot assume role, after someone added `environment:` to the deploy job | A job that uses a GitHub Environment gets a **different** OIDC `sub` (`repo:HerHealthGPT/herhealthgpt:environment:<name>`), so the trust condition on `ref:refs/heads/main` no longer matches | `deploy.yml` deliberately has no `environment:`. If one is ever added, change the `sub` condition in `deploy_trust` (`iam_oidc.tf`) in the **same commit**. Do not widen it to a wildcard to make it work |
| `terraform apply`: `EntityAlreadyExists` for the GitHub OIDC provider | The account already has one for `token.actions.githubusercontent.com` | §1: run `aws iam list-open-id-connect-providers`, set `create_github_oidc_provider = false`, apply again |
| Terraform workflow: the `plan` job shows as skipped | The plan role is off by default, or its repository variables are unset | Expected. §5, "The plan role" |
| SSM: `InvalidInstanceId` / not connected | Host not registered yet, or instance role/internet missing | Wait 2–3 min after boot; `aws ssm describe-instance-information`. If it never appears: EC2 console → Actions → Monitor and troubleshoot → Get system log (shows cloud-init and the bootstrap output) |
| deploy.sh: "secret '…' is empty", or AWS says it "can't find the specified secret value" | §4 not done (a secret with no value yet) | `put-secret-value` the named secret |
| deploy.sh: "GB free after pruning" | Disk full | §9 |
| deploy.sh: "cannot reach the database ... Is RDS stopped?" | RDS is stopped (or its security group changed) | Start RDS, wait for `available`, re-run. Nothing was changed. |
| deploy.sh logs "ACME_CA is overridden ... will NOT verify the certificate" | `ACME_CA` set in `/opt/herhealth/local.env` (staging CA) | Intended only while rehearsing; remove it and redeploy before real use |
| Caddyfile change not taking effect | Should not happen: the directory is mounted | `cat /opt/herhealth/caddy/Caddyfile` and `docker exec herhealth-caddy-1 cat /etc/caddy/Caddyfile` must match |
| deploy.sh: pull fails `no basic auth credentials` / `denied` | ECR login or instance-role policy | `aws sts get-caller-identity` on the host; confirm the instance profile |
| deploy.sh: rolled back | New release failed its health check | Read the output above the rollback line, then `docker logs` / CloudWatch |
| `/health` returns 503 from api. | Backend cannot reach the database | RDS stopped? (§10, auto-restarts after 7 days). Password rotated and not yet picked up? `sudo /opt/herhealth/refresh-secrets.sh --restart-on-change` |
| Browser: certificate warning | Caddy still issuing, or Let's Encrypt rate limit, or staging CA left on | `docker logs herhealth-caddy-1`; check `/opt/herhealth/local.env`; §11 |
| Signup email never arrives; backend logs `AccessDenied` on `ses:SendEmail` | The `ses:FromAddress` condition did not match the `Source` the app sends (`HerHealthGPT <no-reply@…>`) | Unverified until the first real send. Check the denied action's context in CloudTrail; if the condition is the cause, remove it from `ses.tf` and apply |
| Signup email: `NoCredentialsError` | IMDS hop limit too low for containers | `metadata_options.http_put_response_hop_limit` must be 2 (`ec2.tf`) |
| Replies to a code email bounce | No inbound mail exists for `support@herhealthgpt.org` | Known open item — pre-demo checklist |
| Retrieval container restarts | Out of memory (`mem_limit: 4g`) | `docker stats`, `dmesg \| tail`; consider `t3.xlarge` (`instance_type`) |
| Triage answers say nothing about a feature | Its only evidence rows are NHS | Expected — [the NHS decision](#the-nhs-decision) |
| Site down, EC2 status check failing | Host or hardware fault | System check: auto-recovers (alarm). Instance check: reboot via console/SSM |
| Cost higher than expected | t3 unlimited CPU credits, forgotten stopped RDS restarting, large retrieval image retention | Billing console → cost by service; alarm and budget mails |

## 15. Pre-demo checklist

Tick these before showing the site to anyone.

- [ ] **Inbound mail for `support@herhealthgpt.org` works.** Today there is no MX
      record at the apex, so **mail to that address bounces** — including mail
      from AWS to the account's SES contact address, and replies from users to
      verification emails (the app sets it as Reply-To). Decide how it is
      received (forwarder, mailbox provider, …), publish the records, and send
      yourself a test. **Open item — not done by this repo.**
- [ ] The SNS confirmation email is clicked and a test alarm reaches you (the
      Budget alert needs no confirmation; check its mail is not in spam).
- [ ] A real verification email is sent and received through the deployed site
      (also proves the `ses:FromAddress` condition).
- [ ] Google sign-in works from `https://herhealthgpt.org` (§ Google sign-in).
- [ ] `https://www.herhealthgpt.org` redirects to the apex; both certificates
      are valid (not staging).
- [ ] `https://api.herhealthgpt.org/health` returns 200.
- [ ] One full triage conversation completes (retrieval + OpenRouter).
- [ ] The retrieval image's labels show the expected index version and bge-m3
      revision (`docker inspect`, §13).
- [ ] Known statement gaps are understood: DMARC is `p=none`; bounce/complaint
      SNS handling is not built (the account suppression list covers the effect);
      the knowledge base is source-traceable but **not clinician-adjudicated**,
      and retrieval in production excludes NHS text.
- [ ] If the demo is far off, decide: stop EC2 and RDS (§10) and set a reminder
      for RDS's 7-day auto-restart.

## Cost, for orientation

About **$93/month** running 24/7 on `t3.large` (EC2 ≈ $61, RDS ≈ $14, EBS (60 GB)
and Elastic IP ≈ $8, ECR ≈ $3, the rest small); about $18 stopped; a few dollars
destroyed. Figures are from public list prices and need re-checking before being
quoted. The AWS Budget alerts at 80% of `monthly_budget_usd` (default $120).
