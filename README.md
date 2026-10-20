# HerHealthGPT

A multilingual reproductive-health **triage and informational guidance**
system, in English, Arabic and French. Live at
[herhealthgpt.org](https://herhealthgpt.org).

Master's capstone, School of Computing, Queen's University. Group 1-RF, Team 4.
Supervisor: Dr. Rahatara Ferdousi. Mentors: Deloitte Innovation Hub, Egypt.

> **Scope, stated once and enforced everywhere.** This system assesses
> *urgency* and provides *information*. It does not diagnose. No file, comment,
> docstring, string literal, commit message or UI copy may describe it as doing
> so. Its output is an urgency action code and a cited explanation, or an
> informational answer, never a conclusion about what a user has.

**Status (2026-10-20).** Deployed on AWS and running on local models served
from the campus GPU server. A woman describes a concern; the system asks a few
questions and says how urgently to seek care and why, with citations, or
answers a general question as a sourced information page. Accounts, a profile,
cycle data imported from a tracking app, and kept files are built. The whole
interface is in English, Arabic (right-to-left) and French.

### Start here

| If you want to… | Read |
|---|---|
| **Know what runs, on what, with which versions** | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) |
| Follow one message through every layer, with ten traced examples | [`docs/experiments/2026-10-19-traced-consultations.md`](docs/experiments/2026-10-19-traced-consultations.md) |
| Run it locally | [`docs/runbooks/running-the-app.md`](docs/runbooks/running-the-app.md) |
| Serve the models on the GPU server | [`docs/runbooks/uni-server-vllm.md`](docs/runbooks/uni-server-vllm.md) |
| Deploy or operate production | [`docs/runbooks/aws-deploy.md`](docs/runbooks/aws-deploy.md) |
| Know what has been measured, and the limits | [`docs/DATASHEET.md`](docs/DATASHEET.md) |
| Understand the knowledge base | [`docs/KNOWLEDGE_BASE.md`](docs/KNOWLEDGE_BASE.md) |
| Find your way around the repository | [`docs/REPO_MAP.md`](docs/REPO_MAP.md) |
| Know why a decision was made | [`docs/adr/`](docs/adr/) |
| The binding project rules | [`CLAUDE.md`](CLAUDE.md) |

---

## Why it is built this way

A general-purpose multilingual model was evaluated on a 540-case-per-language
benchmark of women's-health concerns:

- **Under-triage 0.718 in English.** Of cases whose correct answer was "see a
  doctor", 72% were routed to "routine".
- Aggregate risk accuracy 0.667 against a majority-class baseline of 0.644: the
  accuracy number hid the safety failure.
- Fine-tuning collapsed clarification-seeking from **0.856 to 0.000** and
  pushed French and Arabic under-triage to **0.994**.
- Cross-language consistency *improved* during that collapse.
  **Consistency alone is not a safety metric.**

So: **under-triage is the dominant failure mode**, and wherever a design choice
trades false alarms against missed escalations, false alarms win.
Cross-language comparison is on the action code, never on text.

## How it works

1. **She writes in her own words.** Retrieval finds passages from the sources;
   a small model call reads what her message answers, as values from a closed
   list of features.
2. **The model decides, grounded.** The base model (`Qwen/Qwen3.5-9B`) chooses
   to ask one question, conclude with an urgency level, answer an
   informational question, or decline an off-topic one
   ([ADR 0011](docs/adr/0011-controller-free-triage.md),
   [ADR 0018](docs/adr/0018-local-models-decide-and-the-adapter-answers.md)).
   It sees what she has answered, the authored evidence those answers match,
   the warning-sign rules that have fired or are one answer away, a ranked
   menu of questions, and the retrieved passages. It can only reply in the
   `TriageDecision` shape, whose ids must come from the knowledge files.
3. **Code checks the decision.** Gates send a reply back when it ignores a
   fired warning sign, repeats a question, concludes too early, explains when
   she described symptoms, or declines something that may be in scope. If a
   warning sign has fired and the model still does not escalate, **code
   concludes at the rule's urgency**. The reply is then validated against the
   knowledge base and capped by what its sources support.
4. **She sees** a question, an urgency with its reasons and sources (the
   rule's quote, the authored evidence rows, the passages), or an information
   page with "when to get help".

Four urgencies, and nothing else: `SELF_CARE`, `ROUTINE_APPOINTMENT`,
`URGENT_SAME_DAY`, `EMERGENCY`. A conclusion may say her answers "match
patterns our sources associate with" a condition, never that she has it.

**Cycle data.** She can import an export from her period-tracking app (our
CSV template, Apple Health's export or shared PDF, or other files read by the
model). Only dates, flow and a closed list of symptoms are kept, after she
confirms; fresh data answers questions she would otherwise be asked, and
asking about it gets a code-written breakdown
([ADR 0019](docs/adr/0019-cycle-data-is-imported-from-any-tracker-and-may-pre-fill-answers.md)).
She may also keep a copy of a file for 30 days
([ADR 0020](docs/adr/0020-she-may-keep-an-uploaded-file-for-30-days.md)).

---

## Architecture

Full detail, with hardware, flags and versions:
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

| Part | Stack | Runs on |
|---|---|---|
| Frontend | Next.js 16, React 19, Tailwind 4; responsive web app, **not a PWA** | EC2 (Docker) |
| Backend | FastAPI, Python 3.12, SQLAlchemy, LangChain; FAISS index in-process | EC2 (Docker) |
| Database | PostgreSQL 16 | AWS RDS |
| Models | vLLM 0.28 | campus GPU server, 4 × NVIDIA A16, reached through Cloudflare tunnels |
| Proxy, TLS | Caddy, Let's Encrypt | EC2 |
| Email | Amazon SES | AWS |

### Models

| Role | Model | Served |
|---|---|---|
| Extract, decide, write information pages | [`Qwen/Qwen3.5-9B`](https://huggingface.co/Qwen/Qwen3.5-9B) | vLLM :8002, tensor parallel 2 |
| Comparison mode B only (plain chat) | fine-tuned LoRA [`herhealthgpt/qwen3.5-9b-herhealth-enfrar-lora-v2`](https://huggingface.co/herhealthgpt/qwen3.5-9b-herhealth-enfrar-lora-v2) (private) | same process, as `herhealth` |
| Retrieval embeddings | [`Qwen/Qwen3-Embedding-4B`](https://huggingface.co/Qwen/Qwen3-Embedding-4B) | vLLM :8003 |
| Reranker (off: no measured gain) | [`Qwen/Qwen3-Reranker-4B`](https://huggingface.co/Qwen/Qwen3-Reranker-4B) | vLLM :8004 |

**The fine-tuned adapter is not on the product path.** It was trained on 2,700
single-turn answers and never shown a clarifying question, so it may not
decide until it is retrained on multi-turn data; and since 2026-10-13 the base
model writes information pages too, because it was faster and did not copy
passages. The adapter answers only in comparison mode B.

**The decision is not constrained by guided decoding.** The model is asked for
JSON, and the backend parses, repairs, validates and retries.

### Rules that hold across the code

- **Nothing outside `packages/contracts/` is imported across services.** A
  convention kept by review; no import-linter runs today.
- **No model weights load in the backend**; every model call is HTTP to vLLM.
- **Policy is data.** The clinical knowledge is in `knowledge/` as YAML and
  CSV, so a clinical change is a reviewable diff.
- **Deploy:** merge to `main` → CI builds images tagged with the git SHA →
  pushed to ECR → the host migrates, switches, health-checks and rolls back by
  itself on failure. Rollback by hand is `git revert`. Nothing is edited on the
  server. `terraform apply` is run by hand, never by CI.

## Repository layout

```
herhealthgpt/
├── services/
│   ├── frontend/        Next.js web app (en / ar / fr)
│   ├── backend/         FastAPI: triage agent and gates, retrieval, accounts,
│   │                    profile, cycle data, kept files, evaluation tools
│   └── data/            ingestion, evidence batches, evaluation cases and scripts
├── packages/contracts/  Pydantic schemas shared across services
├── knowledge/           the seven knowledge files
├── scripts/             serve-models.sh and tunnel-models.sh (GPU server), hygiene
├── infra/               compose files, env templates, Caddy, host deploy scripts,
│                        model serving config, Terraform
├── docs/                architecture, ADRs, runbooks, experiments, datasheet
└── .github/workflows/   path-filtered CI and the deploy
```

`raw/`, `build/` and `infra/envs/*.env` are git-ignored.

---

## The knowledge model

Seven files in `knowledge/`, validated against the Pydantic schemas in
`packages/contracts/`. Counts read from the files on 2026-10-20:

| File | Rows | What it is |
|---|---|---|
| `features.yaml` | 39 | everything the system may ask about |
| `conditions.yaml` | 19 | everything a conclusion may name as a matching pattern |
| `evidence.csv` | 150 | the sparse grid connecting them |
| `red_flags.yaml` | 17 | warning-sign rules, from explicit escalation language only |
| `sources.yaml` | 5 | provenance, licence, precedence |
| `actions.yaml` | 4 | the four action codes, resolved per locale |
| `weights.yaml` | — | ordinal weights (used by the retired controller) |

Five evidence weights and nothing else: `strong_support`, `weak_support`,
`neutral` (meaning *omit the row*), `argues_against`, `rules_out`. **No
probabilities**, likelihood ratios or prevalence figures anywhere. Cancers are
deliberately not modelled; warning-sign rules send her to care without naming
why. Locale-specific instructions ("call 111") never appear in a knowledge
file; action codes are resolved per locale. Detail:
[`docs/KNOWLEDGE_BASE.md`](docs/KNOWLEDGE_BASE.md),
[`knowledge/README.md`](knowledge/README.md).

## Verification protocol

**This project has no clinician reviewer.** So every row must restate
something a cited source says; no row may be an independent clinical
judgement.

1. Every row in `evidence.csv` and `red_flags.yaml` carries a `source_id` and a
   verbatim `source_quote`; `make verify-quotes` checks each against the
   fetched page.
2. A second reader confirms the quote supports the row as written. This checks
   provenance, not clinical correctness.
3. A row that cannot be traced to a sentence is deleted, not softened.
4. Anything needing inference beyond the source is out of scope.

Compensating controls: warning signs only from explicit escalation language;
the bar for `SELF_CARE` above the bar for `ROUTINE_APPOINTMENT`; where sources
conflict on urgency the higher wins, recorded in the row's note.

**The knowledge base is source-traceable, not clinician-adjudicated. State this
wherever results are reported.**

## Sources

| Source | Licence | Status |
|---|---|---|
| Office on Women's Health (womenshealth.gov) | US federal, public domain | quoted and retrieved |
| MedlinePlus | public domain, **except** the A.D.A.M. encyclopedia (`/ency/`, excluded by path) | quoted and retrieved |
| NICHD | US federal, public domain (unverified) | quoted and retrieved |
| CDC | US federal, public domain (unverified) | quoted and retrieved |
| NHS website | Crown copyright, no reuse grant | **quoted only**, never retrieved |

NICE CKS, RCOG and ACOG are excluded on their terms. Fetching obeys each
site's live `robots.txt`; raw fetches are immutable
(`raw/{source}/{date}/`). Tests never hit the network.

---

## Running it

Locally (backend, frontend, PostgreSQL, and the models on the GPU server):
[`docs/runbooks/running-the-app.md`](docs/runbooks/running-the-app.md).
Serving the models: [`docs/runbooks/uni-server-vllm.md`](docs/runbooks/uni-server-vllm.md).
Production: [`docs/runbooks/aws-deploy.md`](docs/runbooks/aws-deploy.md).

## Commands

| Command | Does |
|---|---|
| `make install` | `uv sync` from the lockfile |
| `make validate` | check `knowledge/` against the schemas |
| `make evidence` | build `evidence.csv` from the approved batches |
| `make verify-quotes` | check every quote against the fetched pages (needs `make fetch clean`) |
| `make index` | build the retrieval index (needs the embedding server) |
| `make test` / `make test-api` | Python tests without / with the database (about 1,050 in all) |
| `make test-frontend` | install and build the frontend (`npm ci && npm run build`) |
| `make lint` / `make fmt` | ruff, mypy strict on contracts |
| `make migrate` / `make serve` | apply migrations / run the API on `127.0.0.1:8000` |
| `make eval-red-flags` | live red-flag recall, one case per rule |
| `make eval-languages` | same urgency across English, Arabic, French |
| `make trace-turns` | trace consultations through every layer |
| `make eval` | the retired rule-based controller |
| `make hygiene` | the repository hygiene check CI runs on every PR |

## CI

Path-filtered workflows: `backend`, `frontend`, `data`, `terraform` (plan
only), `hygiene` (every PR), and `deploy` on merges to `main`. A frontend
change does not rebuild the backend.

## Evaluation

The benchmark (540 cases per language, six registers) has **silver labels, not
clinician-adjudicated**. Risk labels come from the English text and propagate
by `canonical_case_id`; English keyword rules are never run on translations.

Latest measurements, with their limits, are in
[`docs/DATASHEET.md`](docs/DATASHEET.md). Among them: red-flag recall 17 of 17
rules on the live pipeline; the same urgency in all three languages on the 6
of 10 scripted consultations that concluded in all three, and none lower than
English.

## Language scope

The interface is fully translated into English, Arabic and French. The chat
replies in the language she writes in. Question wording is authored in
English and rendered by the model at response time; the schema allows authored
`fr`, `ar` and `ar_eg` wording later without migration. **Arabic and French
output has not been reviewed by a native speaker.** Egyptian-Arabic benchmark
text already exists and is not generated.

## Safety, privacy and licensing

- **Not a diagnostic device, and not a substitute for clinical assessment.**
- **Bias toward escalation.** False alarms win over missed escalations.
- **Warning signs are enforced in code** once her answers satisfy a rule; that
  depends on her answer being read correctly, which is measured, not proven.
- **Her data** is hers to see, replace and delete, and goes with her account.
- **Licence recorded per source**; NHS text is never ingested.
- **Secrets never enter the repository.** `*.env` is git-ignored;
  `infra/envs/*.env.example` lists the keys with empty values.

## Further reading

- [`CLAUDE.md`](CLAUDE.md): the project rules. Binding.
- [`CONTRIBUTING.md`](CONTRIBUTING.md): environment setup, workflow, branching.
- [`docs/ROADMAP.md`](docs/ROADMAP.md): what is next.
- [`docs/CODE_GUIDE.md`](docs/CODE_GUIDE.md): the modules in detail.
- [`.claude/skills/`](.claude/skills/): constraints on clinical authoring, repo
  conventions and source ingestion.
