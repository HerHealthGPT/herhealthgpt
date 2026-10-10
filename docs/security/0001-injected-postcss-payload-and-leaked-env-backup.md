---
status: open — credentials NOT yet rotated; purge verified in a mirror, not yet applied or pushed
found: 2026-10-10
updated: 2026-10-11
---

# Two issues from one bad commit: an injected postcss payload and a leaked env backup

Audit run 2026-10-10 after Windows Defender quarantined
`services/frontend/postcss.config.mjs`, which broke the frontend build (every
page returned HTTP 500). The quarantine was the symptom. Two separate problems
sat underneath it, and **the second is the more serious of the two.**

| | issue | severity | status |
|---|---|---|---|
| **1** | Foreign crypto/blockchain code committed into the repo, flagged by Defender as `Trojan:NPM/PolinRider.DGA!MTB` | high | removed from the working tree; stale branches and history outstanding |
| **2** | `infra/envs/backend.env.bak` committed to `main` with **live** API keys and the session secret | **critical** | file removed from the working tree; rewrite written and verified in an isolated mirror; **credentials still not rotated, and the force-push is yours** |

---

## Issue 2 first, because it needs action today

`infra/envs/backend.env.bak` has been tracked on `main` and on every branch
since 2026-09-17. It contains real values, not placeholders. Each was compared
by SHA-256 against the live `infra/envs/backend.env`:

| key | leaked value is… | note |
|---|---|---|
| `OPENROUTER_API_KEY` | **identical to the live key** | a real `sk-or-v1…` key. Rotate. |
| `HERHEALTH_SESSION_SECRET` | **identical to the live secret** | signs access tokens. Rotate — it invalidates existing sessions, which is acceptable. |
| `HERHEALTH_VLLM_API_KEY` | **identical to the live token** | the JupyterHub proxy token. It rotates on Jupyter restart anyway, but treat it as burned. |
| `HERHEALTH_DATABASE_URL` | identical to live | **low risk**: it is the `localhost:5432` dev default already published in `backend.env.example`. No production credential here. |
| `HERHEALTH_GOOGLE_CLIENT_ID` | identical to live | **not a secret.** An OAuth client *id* is public by design. No action. |

So three credentials genuinely need rotating: the OpenRouter key, the session
secret, and the vLLM/JupyterHub token.

**Why this slipped through.** `.gitignore` had `.env` and `*.env`, and
`backend.env.bak` matches neither — it ends in `.bak`. CLAUDE.md states *"No
key, token or secret is ever committed to this repo"*, and the rule was right;
only the glob was wrong. Fixed: `*.bak` and `*.env.bak` are now ignored, with a
comment saying why both lines are there.

### What you need to do

1. **Rotate the three credentials now.** Do this before the history purge —
   rotation is what actually protects you. A key that has sat in a GitHub repo
   should be assumed scraped whether or not the repo was ever public.
2. **Check whether the repo has ever been public**, and look at GitHub's secret
   scanning alerts and the org audit log for unexpected access since 2026-09-17.
3. **Purge the file from history** — prepared and verified on 2026-10-11; see
   *The history purge* below for the exact commands and the order to run them
   in.
4. Three other tracked `.bak` files remain — `knowledge/red_flags.yaml.bak`,
   `services/data/ingest.lock.jsonl.bak`,
   `services/data/ingest_targets.yaml.bak`. None contain secrets; they are
   accidental editor backups from the same commit. The new `.gitignore` rule
   does not untrack them, so remove them when convenient. A stale 459-line
   `red_flags.yaml.bak` next to a reviewed knowledge file is a trap for a
   future reader.

---

## Issue 1: what the injected file actually was

### Root cause

**Two sibling commits**, both 2026-09-17, both by hanaessam, both titled *"Add
ingest_targets.yaml and Dockerfile for retrieval service"*: **`9f58945`** and
**`bb818ca`**. They are duplicates of the same work, and which one a branch
inherited decides how it was contaminated — `bb818ca` is the ancestor on `main`
and `backend`, `9f58945` only on `data`, and `data` has both. Alongside their
legitimate work (the backend Dockerfile, migration `0010`, agent/clients/routes
changes) they also added:

- `public/` at the repo root — 17 files from **an unrelated "Blockchain
  Explorer" application**. Its own `public/fonts/README.md` says so outright:
  *"This directory contains custom fonts for the Blockchain Explorer
  application"*, referencing `BlockchainFont`, `TechMono` and a
  `public/index.html` that does not exist here.
- `services/frontend/postcss.config.mjs` rewritten from 94 bytes to **32,734
  bytes**, of which one line is 32,566 characters.
- `infra/envs/backend.env.bak` (issue 2).
- Two off-topic research PDFs in `docs/research/sources/`.

This is the signature of `git add -A` run in a working directory that also held
another project's files. Nothing suggests this repo was targeted.

### What the payload contains

Characterised without ever printing it, since reproducing the bytes causes
Defender to quarantine whatever file they land in — that is what was eating
this audit's own intermediate output:

- 2,397 `0x` hex literals, no 40-hex wallet addresses — consistent with a
  constant table in a bundled crypto library.
- One reference to `process.env.ETH_RPC_URL` — an Ethereum RPC endpoint.
- `createRequire(import.meta.url)` plus 6 `require(` calls — bundler output.
- **No** `eval`, `atob`, `Buffer.from`, `child_process`, `exec`, `fetch`,
  `XMLHttpRequest`, `os.homedir`, `setInterval`, or any token/credential
  keyword.

A second file carries the same marker: **`public/fonts/fa-solid-600.eot`**,
32,540 bytes. It is not a font. Font Awesome's solid weight is **900** —
`fa-solid-900.*` is present with its full `.eot/.svg/.ttf/.woff/.woff2` set,
whereas `fa-solid-600` exists only as a lone `.eot` with no siblings, and the
commit diff records it as **one added text line** where every real font shows as
`Bin`. Defender locked it too.

**Honest reading of the evidence.** Defender's `!MTB` suffix marks a machine-
learning/behavioural detection, and those do fire on minified crypto bundles. So
this may be a true detection of a malicious blockchain-explorer template, or a
false positive on an innocent one. The audit cannot settle that, and it does not
need to: **32 KB of unrelated Ethereum code executing inside the frontend build
is unacceptable either way**, and the team already judged it so in PR #47.

Fingerprints, if you want a VirusTotal second opinion:

| file | SHA-256 |
|---|---|
| `postcss.config.mjs` payload | `7a106f6500a3f98718efa068c04bd662c5fc95e706fd7c4a18e04b59886a264a` |
| `public/fonts/fa-solid-600.eot` | `1a96780626843eb4fed452d17b5c302b3c8cf78013ee70cc470a88e215ba4a52` |

### Where it executed

`postcss.config.mjs` is evaluated by **every** `next dev` and `next build`. So
between 2026-09-17 and the 2026-10-09 fix it ran on each developer machine that
started the frontend, and in CI: `.github/workflows/deploy.yml` builds
`services/frontend` into an image, and that build runs `next build`.

### Timeline, and the re-infection

`services/frontend/postcss.config.mjs`, by size:

| commit | date | author | size |
|---|---|---|---|
| `747ccff` | 2026-09-01 | hanaessam | 94 — legitimate |
| `9f58945` | 2026-09-17 | hanaessam | **32,734 — contamination** |
| `28ff078` | 2026-10-09 | MariamPhilip66 | 94 — *"remove injected code"* (PR #47) |
| `35ff832` | 2026-10-10 | Mariam Philip | 94 — still clean |
| **`2a9bd95`** | **2026-10-10** | **hanaessam** | **32,734 — re-introduced** |
| `acf985e` | 2026-10-10 | hanaessam | 32,734 — survives the merge of clean `main` |

**The re-infection was a merge, not malware.** `2a9bd95` is *"Merge branch
'backend' of github.com/HerHealthGPT/herhealthgpt into backend"* — merging the
stale remote `backend` into the local one, and the resolution took the infected
side. The next merge of `main` then kept it, because the infected side now held
the newer change to that file. Checked and confirmed: **no npm lifecycle hooks
exist in any tracked `package.json`** (no `preinstall`, `postinstall`,
`prepare`), so there is no mechanism re-writing these files on their own.

This corrects my first read of the situation, which was that something was
actively re-injecting. It was not. That is a genuinely better position to be in.

### Which branches are still infected

`main` is **clean** on both counts — the payload and the foreign `public/` tree.
These still carry the payload:

| ref | why |
|---|---|
| `backend`, `origin/backend` | **contained the fix and regressed past it** (`2a9bd95`) |
| `data`, `origin/data` | branched before the fix |
| `origin/frontend` | branched before the fix |
| `origin/deploy/aws-ec2`, `origin/deploy/build-index-in-ci`, `origin/deploy/first-production` | branched before the fix |
| `origin/fix/build-index-tolerate-nhs`, `origin/fix/lint-import-order`, `origin/fix/oidc-sub-with-ids`, `origin/fix/retrieval-cpu-torch` | branched before the fix |

The nine stale ones are mostly merged or abandoned — deleting them is the
cheapest fix. `data` and `backend` are live and need the clean file carried
onto them, which is what the working tree now holds.

---

## What was changed in the working tree

Not committed — this repo's convention is that commits are the owner's.

| change | why |
|---|---|
| `services/frontend/postcss.config.mjs` → the legitimate 94-byte Tailwind v4 config (exact content from `28ff078`) | restores the frontend build without restoring the suspect bytes |
| root `public/` deleted (17 files, including `fa-solid-600.eot`) | foreign project; nothing in this repo references it, and the real one is `services/frontend/public/` |
| `infra/envs/backend.env.bak` deleted | issue 2 |
| `.gitignore` — added `*.bak` and `*.env.bak` with a comment | closes the exact glob gap that leaked the keys |

Verified afterwards: no file in the working tree contains `ETH_RPC_URL`;
`postcss.config.mjs` is 94 bytes; 559 offline tests and 96 contract tests pass;
Postgres, retrieval (`:8001`), backend (`:8000`) and frontend (`:3000`,
including `/chat`) all healthy.

## Prevention — what now blocks this

Built 2026-10-11. `make verify-quotes` and the evidence review gate protect
`knowledge/` carefully; there was no equivalent gate on application files, and
both of these issues arrived through that gap. There is one now.

**`scripts/check_repo_hygiene.py`** — stdlib-only, offline, five rules, each
written against a specific thing that actually happened:

| rule | catches | the original |
|---|---|---|
| `env-file-committed` | any committed file with `env` as a dot-separated name part, unless it ends `.example` | `backend.env.bak` |
| `credential` | vendor key shapes (`sk-or-v1`, `AKIA…`, `ghp_…`, private-key blocks) anywhere, plus `NAME=<opaque>` in config files | the three live keys |
| `minified-blob` | any line over 5,000 characters outside SVG/JSONL/lockfiles/archived pages | the 32,566-character payload |
| `unexpected-root-entry` | a top-level entry not on an explicit allowlist | root `public/` |
| `text-posing-as-binary` | a `.eot`/`.ttf`/`.png`/`.pdf`/… containing no NUL byte | `fa-solid-600.eot` |

*Why a script and not gitleaks or a scanning action.* The incident was foreign
code arriving through an unwatched path. A third-party scanner would mean
trusting another supply chain to fix a supply-chain problem, and would need a
network fetch on every run. Five rules over the stdlib are auditable in one
sitting. Reach for a real scanner when these stop being enough.

*Calibration.* Run against the repo as it stood, the checker independently
re-found both halves of the incident — 17 `public/` files and
`backend.env.bak` — and reported **nothing else**. Four initial false positives
were each fixed by narrowing a rule, not by suppressing a file: PDFs open with
~10 KB of ASCII before their first NUL (so the binary test reads the whole
blob), vendor docs carry example credentials (so archived-source trees are out
of scope for secret scanning), Alembic's `migrations/env.py` is a module not an
env file (so source extensions are excluded), and real placeholders are
hyphenated phrases like `test-only-session-secret-do-not-use-in-production`
(so the placeholder pattern allows `-` and `.`). A check that cries wolf gets
disabled, and a disabled check is how this happened.

**Where it runs:**

- `.github/workflows/hygiene.yml` — the only workflow here with **no path
  filter and no branch filter**. Both omissions are the point: `public/` and
  `infra/envs/**` matched none of the existing filters, and the payload
  survived on nine stale branches that a main-only check would have passed.
- `.githooks/pre-commit` — the same check against the staged tree, enabled per
  clone with `git config core.hooksPath .githooks`. A convenience, not the
  control: `--no-verify` skips it. CI cannot be skipped.
- `make hygiene` — to run it by hand.

**`.github/workflows/frontend.yml`** also now exists, because the frontend had
no PR-time checks whatsoever: `services/frontend/**` appeared only in
`deploy.yml`, which builds *after* a merge to main. `npm ci && npm run build`
is the gate (the build type-checks too). Lint is reporting-only until the four
pre-existing `react-hooks/set-state-in-effect` errors are fixed.

**Still worth doing, and not done:**

- The frontend has **no test runner** — no jest, no vitest, no `test` script.
  "Testing" it currently means compiling it. Adding real component tests for
  the triage card and bubble rendering is the obvious next step.
- Review large diffs by file list, not line count. `git show --stat` on the
  contamination commit would have shown 17 font files and a 32 KB postcss
  config under a message about a Dockerfile.
- Turn on GitHub push protection / secret scanning as a second, independent
  layer. Our check only sees what reaches CI; push protection rejects at the
  server.

---

## The history purge

Run and verified **2026-10-11**, in an isolated mirror clone — the real
repository was not modified, because it held 32 paths of uncommitted work and a
stash, and a rewrite requires a clean tree.

`git filter-repo` is not installed here and installing it (or BFG) needs a
network fetch, so the rewrite used `git filter-branch --index-filter`, which
ships with git. For 123 commits and a single path that is entirely adequate; the
deprecation warnings on `filter-branch` are about performance and footguns on
large repositories.

```bash
git filter-branch --force   --index-filter 'git rm --cached --ignore-unmatch infra/envs/backend.env.bak'   --tag-name-filter cat -- --all
```

`--prune-empty` was deliberately **omitted**: both adding commits carry plenty
of other content, so nothing becomes empty, and leaving it off keeps the commit
graph provably unchanged apart from the removed blob.

### Verification of the rewritten mirror

| check | before | after |
|---|---|---|
| refs holding `infra/envs/backend.env.bak` | 17 of 20 | **0** |
| commits touching that path (full history) | 4 | **0** |
| leaked blob `013333d9` present in object store | yes | **no** |
| blobs containing the live OpenRouter key | 1 | **0** |
| blobs containing the live session secret | 1 | **0** |
| commit count | 123 | 123 |
| ref count | 21 | 21 |
| **per-ref tree hash, excluding the removed path** | — | **identical on all 20 refs** |

The secret scan was run against both repositories with the same command, so the
`1 → 0` result is a controlled comparison rather than an assertion that the
check works.

### Two consequences to expect

- **30 of the 123 commits are GPG-signed** — GitHub's own signatures on web-UI
  merge commits — and a rewrite cannot preserve them. All 30 will show as
  unverified afterwards. This is true of `filter-repo` and BFG too, not a
  quirk of the tool chosen here.
- **Every commit SHA from 2026-08-03 onward changes**, including on branches
  that never held the file (`frontend`, `chore/repo-phase-1-scaffold`). Their
  trees are bit-identical; only commit identity moves, because one rewritten
  ancestor renames all its descendants. Tip SHAs: `main` 35ff832 → 270653e,
  `data` a652990 → 4a9bf98, `backend` acf985e → f0b2bb6, `frontend` 6af488f →
  f028a34. Everyone else must re-clone, and open PRs will need reopening.

### The order to run it in

The rewritten mirror is a verified artefact, not the thing to push. Because the
working tree has uncommitted work, the clean path is to redo the identical
rewrite in place once that work is committed — one rewrite, one force-push, no
divergence between local and remote.

1. **Rotate the three credentials.** Independent of everything below, and the
   only step that actually protects them.
2. **Commit the pending work** (the `inform` shape, the payload cleanup, the
   `.gitignore` fix) and decide what to do with `stash@{0}` — apply it or drop
   it. A stash is a commit against the old graph, so a rewrite orphans it.
3. **Back up, then rewrite in place** on a clean tree:
   ```bash
   git bundle create ../herhealthgpt-pre-purge.bundle --all   # keep this
   git filter-branch --force      --index-filter 'git rm --cached --ignore-unmatch infra/envs/backend.env.bak'      --tag-name-filter cat -- --all
   git for-each-ref --format='%(refname)' refs/original | xargs -n 1 git update-ref -d
   git reflog expire --expire=now --all && git gc --prune=now
   ```
4. **Verify** before pushing anything — this must print `0`:
   ```bash
   git log --all --full-history --oneline -- infra/envs/backend.env.bak | wc -l
   ```
5. **Force-push** the branches you are keeping, e.g.
   `git push --force-with-lease origin main data backend frontend`.
6. **Delete the stale branches** rather than rewriting and pushing each: the
   nine listed above are merged or abandoned, and deleting is cheaper and
   safer than nine more force-pushes.
7. **Ask GitHub Support to garbage-collect** the old objects. Deleting a branch
   does **not** remove its commits — GitHub keeps them reachable by SHA, and in
   forks and PR refs, until it runs GC. Until that happens the old blob is
   still retrievable by anyone who knows the SHA, which is exactly why step 1
   is not optional.
