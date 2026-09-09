# HerHealthGPT

A multilingual reproductive-health **triage and informational guidance** system.
English, French, Arabic.

Master's capstone, School of Computing, Queen's University. Group 1-RF, Team 4.
Supervisor: Dr. Rahatara Ferdousi. Mentors: Deloitte Innovation Hub, Egypt.

> **Scope, stated once and enforced everywhere.** This system assesses *urgency*
> and provides *information*. It does not diagnose. No file, comment, docstring,
> string literal, commit message or UI copy may describe it as doing so. Its
> output is an urgency action code and a cited explanation — never a conclusion
> about what a user has.

**Status: Phase 2 complete — knowledge base and triage controller.**
All seven knowledge files are authored and validated: 37 features, 19
conditions, 135 evidence rows, 16 red-flag rules, 5 sources, **151/151 quotes
verified verbatim** against their cited source. The stopping controller and the
evaluation harness are built and tested (399 tests). Counts as of 2026-08-19 —
see `CLAUDE.md` for what changed and why.

**Not built yet:** retrieval, model serving, API, frontend. See
[`docs/ROADMAP.md`](docs/ROADMAP.md).

### Start here

| If you want to… | Read |
|---|---|
| **Start every local service and test Base / Fine-tuned** | [Run the full app](#run-the-full-app-local-laptop) · [Fine-tuned on campus](#fine-tuned-model-campus-vm--laptop) |
| Understand how the reasoning works, **with diagrams** | [`docs/KNOWLEDGE_BASE.md`](docs/KNOWLEDGE_BASE.md) |
| Find your way around the repository | [`docs/REPO_MAP.md`](docs/REPO_MAP.md) |
| Know what we are doing now and next | [`docs/ROADMAP.md`](docs/ROADMAP.md) |
| Read every module in detail | [`docs/CODE_GUIDE.md`](docs/CODE_GUIDE.md) |
| Know why a decision was made | [`docs/adr/`](docs/adr/) |

Offline controller smoke test (no GPU, no chat UI):

```bash
make install
make triage CASE=services/backend/cases/sudden_severe_pain.yaml
```

---

## Table of contents

- [Why it is built this way](#why-it-is-built-this-way)
- [How it reasons](#how-it-reasons)
- [Architecture](#architecture) (includes [Models this project uses](#models-this-project-uses))
- [Repository layout](#repository-layout)
- [The knowledge model](#the-knowledge-model)
- [Verification protocol](#verification-protocol)
- [Sources](#sources)
- [Quickstart](#quickstart)
- [Run the full app (local laptop)](#run-the-full-app-local-laptop)
- [Fine-tuned model (campus VM + laptop)](#fine-tuned-model-campus-vm--laptop)
- [Commands](#commands)
- [CI](#ci)
- [Evaluation](#evaluation)
- [Roadmap](#roadmap)
- [Language scope](#language-scope)
- [Safety, privacy and licensing](#safety-privacy-and-licensing)
- [Further reading](#further-reading)

---

## Why it is built this way

A general-purpose multilingual model was evaluated on a 540-case-per-language
benchmark of women's-health concerns. The findings drive the architecture:

- **Under-triage 0.718 in English.** Of cases whose correct answer was "see a
  doctor", 72% were routed to "routine".
- Aggregate risk accuracy 0.667 against a majority-class baseline of 0.644 — the
  accuracy number hid the safety failure entirely.
- Fine-tuning collapsed clarification-seeking from **0.856 to 0.000** and pushed
  French and Arabic under-triage to **0.994**: the model predicted "routine" for
  538 of 540 French cases.
- Cross-language consistency *improved* during that collapse, because the model
  had collapsed onto one answer. **Consistency alone is not a safety metric.**

Four consequences, all binding:

1. **No fine-tuning in the MVP.** RAG plus a deterministic controller.
   Fine-tuning is a documented contingency, not a deliverable.
2. **The triage decision lives in Python, not in the model or the prompt.** The
   model extracts feature values and phrases text. It never decides whether to
   ask another question or what urgency to assign.
3. **Under-triage is the dominant failure mode.** Whenever a design choice trades
   false alarms against missed escalations, choose false alarms.
4. **Cross-language comparison is on the action code**, never on text similarity.

---

## How it reasons

A user describes a concern in her own words. The system asks a small number of
clarifying questions, then says how urgently to seek care and why, with
citations. If her answers match a red-flag rule at any point, it escalates
immediately without asking anything further.

**1. Red flags — deterministic, before any model call.** `red_flags.yaml` holds
escalation rules derived *only* from explicit escalation language in a source.
They are plain conditionals, they run first, they cannot be overridden by a
model, and a match short-circuits straight to escalation.

**2. Elimination over a differential — plain Python, no LLM.** Each answer adds
an ordinal weight to a log-odds score per condition. `should_stop` checks in
order, first match wins:

| Step | Check |
|---|---|
| 1 | A red flag fired → escalate, no model call |
| 2 | All conditions above `plausibility_floor` share one action → stop |
| 3 | No unasked feature could change the action → stop |
| 4 | Top plausibility above `stop_confidence`, `stop_margin` clear of second → stop |
| 5 | `max_questions` (6) reached → stop with the differential |
| 6 | Otherwise → ask one question |

One question per turn, always. **Stopping at `SELF_CARE` requires a strictly
higher bar than stopping at `ROUTINE_APPOINTMENT`** — enforced by the schema,
which refuses to load `weights.yaml` if that inequality does not hold.

The reasoning core takes no dependency on a model, a network or a server. It is
driveable from a CLI with a scripted dialogue, which is what makes the evaluation
harness possible.

### Where the model *is* used

Language, not judgement. It interprets free text into feature values, renders
probe questions in the user's language, and phrases the final explanation over
retrieved cited passages. It does not decide urgency.

---

## Architecture

Monorepo. Four independently deployable services, one contracts package.

| Service | Stack | Deployable | Why separate |
|---|---|---|---|
| `services/frontend` | Next.js, responsive web app | yes | Different runtime and build pipeline |
| `services/backend` | FastAPI (Python 3.12) | yes | Triage, tracker, directory, visit prep, retrieval, safety, orchestration |
| `services/model` | vLLM — Qwen3.5-9B, embeddings, reranker | yes | GPU-bound; scales on a different axis |
| `services/data` | Python 3.12 | no — offline | Ingestion, validation, evaluation; runs in CI and by hand |

**The frontend is a normal responsive web app.** No service worker, no manifest,
no offline shell, no install prompt, no web push. Mobile-first layout with RTL
support for Arabic. Do not add PWA scaffolding.

**No model weights load inside the backend process.** Embeddings are an HTTP
call to local `services/model` (bge-m3 on `:8001`). Reasoning is either
OpenRouter (Base tab) or campus vLLM with our LoRA (Fine-tuned tab).

### Models this project uses

| Role | Model | Where |
|---|---|---|
| Base reasoning | [`Qwen/Qwen3.5-9B`](https://huggingface.co/Qwen/Qwen3.5-9B) | OpenRouter in local chat; also the vLLM base on campus |
| Fine-tuned LoRA (experimental) | [`herhealthgpt/qwen3.5-9b-herhealth-enfrar-lora-v2`](https://huggingface.co/herhealthgpt/qwen3.5-9b-herhealth-enfrar-lora-v2) | Private HF repo; served on Lobot as adapter id `herhealth` from `/home/jovyan/models/herhealth-lora-v2` |
| Retrieval embeddings | [`BAAI/bge-m3`](https://huggingface.co/BAAI/bge-m3) | Local `services/model` over `build/index` |

**`Qwen/Qwen3.5-9B` is a multimodal hybrid, not a plain text model.** It loads
as `Qwen3_5ForConditionalGeneration`: a vision tower plus a mixed attention
stack, where only every fourth layer is full attention and the rest are gated
linear-attention (Mamba-family) blocks. This drives real serving flags — both
`image` and `video` must be capped to run text-only, and the KV cache
reconciles two different page sizes. See
[`docs/runbooks/uni-server-vllm.md`](docs/runbooks/uni-server-vllm.md) §0.2.

The LoRA was trained (QLoRA, `r=16`) on six-register styled answers for EN/FR/AR
phrasing. Its module list matches that architecture: MLP projections on all 32
layers, attention projections only on layers 3, 7, 11, 15, 19, 23, 27 and 31. It is **not** cleared to own triage decisions until a multi-turn
retrain is reviewed — see ADR 0011 / ADR 0016 and the Fine-tuned section below.
HF access to the private adapter needs a token with read access to the
`herhealthgpt` org; that token lives on the serving host only, never in this
repo.

### The dependency rule

**Nothing outside `packages/contracts/` may be imported across a service
boundary.** Contracts holds the Pydantic schemas, error codes and safety policy;
both sides depend on it and neither depends on the other. Enforced by
`import-linter` in CI once a second Python service exists.

Inside `services/backend`, the same rule applies by layer — `domain` ← `triage`
← `adapters` ← `api`, dependencies pointing inward only — so the triage core
stays testable without a server, a GPU or a network.

### Policy as data

The clinical reasoning lives in `knowledge/` as declarative YAML and CSV, not in
code. A clinical change is a data diff that can be reviewed, reverted and
regression-tested on its own.

### Deploy

Merge to main → path-filtered CI builds only what changed → image tagged with the
git SHA → PR bumps that tag in `infra/envs/staging.env` → merge triggers a
self-hosted runner on the GPU server. Rollback is `git revert`. Nothing is ever
edited directly on the server.

---

## Repository layout

```
herhealthgpt/
├── services/
│   ├── frontend/            Next.js responsive web app
│   ├── backend/             FastAPI: triage, tracker, directory, visit prep,
│   │                        retrieval, safety, orchestration
│   ├── model/               vLLM: Qwen3.5-9B, embeddings, reranker
│   └── data/                ingestion, validation, evaluation harness
│       ├── src/herhealth_data/
│       │   ├── cli.py       validate / build / eval
│       │   └── ingest/      one module per source (phase 4)
│       ├── eval/cases/      benchmark cases, version-controlled
│       └── tests/
├── packages/
│   ├── contracts/           Pydantic schemas, error codes, safety policy
│   └── types-ts/            TypeScript types generated from OpenAPI
├── knowledge/               the seven hand-authored clinical files
├── infra/                   compose.yml, envs/*.env, Caddy, Prometheus
├── .github/workflows/       path-filtered CI
├── .claude/skills/          binding constraints for humans and agents alike
├── CLAUDE.md                the project spec; binding
├── pyproject.toml           uv workspace root
├── uv.lock                  committed; the source of truth for the environment
└── CONTRIBUTING.md          environment setup, workflow, branching
```

`raw/` and `build/` are gitignored and reproducible from `make fetch build`.

---

## The knowledge model

Seven files in `knowledge/`, validated against the Pydantic schemas in
`packages/contracts/`. **The schemas are the single definition; the files conform
to them, not the other way round.**

| File | Rows | What it is |
|---|---|---|
| `features.yaml` | ~50 | Everything the system may ask about |
| `conditions.yaml` | 14 | Everything the system may consider |
| `evidence.csv` | ~350 | The sparse grid connecting them |
| `red_flags.yaml` | ~25 | Deterministic escalation rules |
| `sources.yaml` | ~15 | Provenance, licence, precedence |
| `weights.yaml` | — | Ordinal-to-log-odds mapping, tunable |
| `actions.yaml` | — | Four action codes, resolved per locale |

Plus `passages.parquet`, generated by ingestion — the only artifact produced at
scale.

### The five evidence weights, and nothing else

```
strong_support   weak_support   neutral   argues_against   rules_out
```

**No probabilities.** No likelihood ratios, prevalence figures or confidence
scores anywhere. `neutral` means **omit the row**: 14 × 50 is 700 possible cells
but only ~350 carry meaning.

### The four action codes, and nothing else

```
SELF_CARE   ROUTINE_APPOINTMENT   URGENT_SAME_DAY   EMERGENCY
```

Locale-specific instructions — "call 111", "see your GP" — never appear in a
knowledge file or a stored passage. Source content is UK and US; users are in
Egypt. Codes are resolved per locale at response time.

### Why the `argues_against` rows matter

Without "regular periods `argues_against` PCOS", PCOS never drops out of the
differential and elimination does not work. But sources list what a condition
*causes*; they rarely state what argues against it. So an `argues_against` row is
only written when a source explicitly frames the feature as distinguishing,
excluding, or characteristic of an alternative — never inferred from absence in a
symptom list. **If in doubt, omit the row.** A missing row is neutral, which is
safe.

### Conditions covered

Phase 1 hand-authors three; the feature set extends to all fourteen without
migration.

| | Condition | | Condition |
|---|---|---|---|
| 1 | **PCOS** *(phase 1)* | 8 | Primary ovarian insufficiency |
| 2 | **Endometriosis** *(phase 1)* | 9 | Pelvic inflammatory disease |
| 3 | **Uterine fibroids** *(phase 1)* | 10 | Endometrial polyp |
| 4 | Adenomyosis | 11 | Inherited bleeding disorder |
| 5 | Hypothyroidism | 12 | Pregnancy-related bleeding |
| 6 | Hyperprolactinaemia | 13 | `normal_variation` |
| 7 | Functional hypothalamic amenorrhoea | 14 | `perimenopause` |

The last two are not conditions in a textbook sense. `normal_variation` exists so
`SELF_CARE` is reachable at all; `perimenopause` so PCOS is not over-suspected in
women over 45. A differential without them systematically over-triages.

---

## Verification protocol

**This project has no clinician reviewer.** That is a resource constraint, and it
changes what the knowledge base is allowed to contain.

> **The rule: every row must be a restatement of something a cited source says.
> No row may be an independent clinical judgement.**

This makes verification a reading-comprehension task rather than a medical one —
which is a task we can actually perform.

1. Every row in `evidence.csv` and `red_flags.yaml` carries a `source_id` **and a
   `source_quote`** holding the sentence or clause it was derived from. Both are
   required by the schema; an empty quote fails to load.
2. A second team member reads the quote and confirms it supports the row as
   written. This checks provenance, not clinical correctness.
3. If a row cannot be traced to a specific sentence, **it is deleted, not
   softened**.
4. Anything requiring inference beyond what the source states is out of scope.
   Gaps are not filled with plausible clinical reasoning.

There is deliberately **no `reviewed_by_clinician` field** or anything resembling
one — such a field could only hold a value we are not in a position to assert.
A test asserts no such field exists.

**Compensating controls**, because unreviewed content means biasing conservative:

- Red-flag rules derive only from explicit escalation language. Never inferred.
- The `SELF_CARE` bar is strictly higher than the `ROUTINE_APPOINTMENT` bar.
- Where sources conflict on urgency, the **higher** urgency wins and the conflict
  is appended to `build/conflicts.jsonl`.
- `DATASHEET.md` states plainly that the knowledge base is source-traceable but
  **not clinician-adjudicated**.

State this limitation wherever results are reported. Do not describe the
knowledge base as clinically validated, expert-reviewed, or verified.

---

## Sources

Terms were read from the sources' own pages on 2026-08-03. **Only usable sources
appear in `sources.yaml`** — the rest were removed rather than listed, so nothing
unusable can be cited by accident.

| Source | Access | Licence | Status |
|---|---|---|---|
| MedlinePlus | Topic pages + topics XML, no key | Public domain **except** A.D.A.M. encyclopedia | **available** |
| NICHD | Pages, no key | US federal, public domain *(unverified)* | **available** |
| CDC | Pages, Socrata token optional | US federal, public domain *(unverified)* | **available** |
| NHS website | Public pages, **manual reading only** | Crown copyright, no reuse grant | **citable_only** |

Two independent facts per source: **precedence** decides who wins a
disagreement, **status** decides whether the source is usable at all.

- `available` — may be quoted **and** ingested into `passages.parquet`
- `citable_only` — may be quoted with attribution; text must **not** enter the corpus

**MedlinePlus has a split licence and it matters.** Topic summaries are public
domain. The A.D.A.M. Medical Encyclopedia (`medlineplus.gov/ency/*`) is not, and
its terms state: *"You may not ingest and/or brand the copyrighted content found
on MedlinePlus in an EHR, patient portal, or other health IT system."* That
clause names systems like this one. **The ingestion client must exclude `/ency/`
by path.** Attribution required: *"Courtesy of MedlinePlus from the National
Library of Medicine."*

**NHS is manual reading only.** No Open Government Licence — the content policy
states only "© Crown copyright". `robots.txt` carries `Disallow: /Conditions/`.
Its "when to get help" sections are the best escalation language available, so it
is quoted with attribution and never ingested.

**Excluded, and why — do not re-investigate:** NICE CKS (UK-only Open Content
Licence; CKS is separately third-party under its own EULA; terms forbid use "for
any commercial gain" and bar use outside the UK without written agreement),
RCOG/ACOG (copyright, permission required), UMLS (licence + account, not needed),
WHO ICD (only resolves `TODO_VERIFY` codes; cosmetic), NCBI E-utilities and
openFDA (out of MVP scope).

**Precedence on conflict** (lower wins): NHS 2, NICHD/MedlinePlus 3, CDC 4.
Numbering gaps are the removed sources. Never resolve a conflict silently.

Raw fetches are immutable: `raw/{source}/{YYYY-MM-DD}/`, never overwritten. Every
record stores `url`, `fetched_at`, `content_hash` and `licence`. Ask before any
network call. **Tests never hit the network.**

---

## Quickstart

Install [uv](https://docs.astral.sh/uv/), [Docker Desktop](https://www.docker.com/products/docker-desktop/),
and [Node.js 20+](https://nodejs.org/) (for the frontend).

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows PowerShell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Then:

```bash
git clone <repo> && cd herhealthgpt
uv sync
cp infra/envs/backend.env.example infra/envs/backend.env
# Edit backend.env: set HERHEALTH_SESSION_SECRET (openssl rand -hex 32),
# OPENROUTER_API_KEY, and HERHEALTH_TRIAGE_MODE=openrouter for real chat.
```

`uv sync` reads `.python-version`, downloads CPython 3.12 if needed, creates
`.venv/`, and installs the lockfile. Prefer `uv run` over activating the venv.

**`uv.lock` is committed and is the source of truth.** CI runs `uv sync
--locked`.

You also need a built retrieval index at `build/index/` (bge-m3). If that
directory is missing, run the data pipeline / index step documented in
[`docs/CODE_GUIDE.md`](docs/CODE_GUIDE.md) before starting `services/model`.

---

## Run the full app (local laptop)

Four processes on the laptop. The campus GPU is **optional** and only needed
for the Fine-tuned tab (next section).

| Process | Port | Role |
|---|---|---|
| PostgreSQL (`infra/compose.yml`) | 5432 | Accounts + triage sessions |
| `services/model` (retrieval) | **8001** | bge-m3 RAG over `build/index` |
| `services/backend` (FastAPI) | **8000** | Triage API, auth, orchestration |
| `services/frontend` (Next.js) | **3000** | Chat UI |

**Order matters.** A turn always calls retrieval on `:8001` *before* the
reasoning model. If `:8001` is down you get `502` / `WinError 10061` even when
campus vLLM is healthy.

### 1. Configure `infra/envs/backend.env`

Minimum for **Base** (OpenRouter) chat:

```env
HERHEALTH_DATABASE_URL=postgresql+psycopg://herhealth:herhealth@localhost:5432/herhealth
HERHEALTH_SESSION_SECRET=<openssl rand -hex 32>
HERHEALTH_EMAIL_SENDER=console
HERHEALTH_TRIAGE_MODE=openrouter
OPENROUTER_API_KEY=sk-or-...
HERHEALTH_MODEL_SERVICE_URL=http://127.0.0.1:8001
HERHEALTH_COOKIE_SECURE=false
HERHEALTH_CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

Add these only when testing Fine-tuned (after campus + Lobot proxy work):

```env
HERHEALTH_MODEL_SELECTOR=on
HERHEALTH_VLLM_URL=https://lobot.cs.queensu.ca/user/group-digi2026-g1/proxy/8000
HERHEALTH_VLLM_MODEL=herhealth
HERHEALTH_VLLM_API_KEY=<JUPYTERHUB_API_TOKEN from the pod — rotates on cull>
```

Keep `HERHEALTH_TRIAGE_MODE=openrouter` when the selector is on: **Base** uses
OpenRouter, **Fine-tuned** uses `HERHEALTH_VLLM_*`. Do not put the pod IP
`10.244.x.x` in `HERHEALTH_VLLM_URL`.

Frontend: set `NEXT_PUBLIC_API_URL=http://127.0.0.1:8000` in
`services/frontend/.env.local` if the UI talks to the API directly (same CORS
origins as above).

### 2. Start PostgreSQL and migrate

```powershell
# From the repo root
docker compose -f infra/compose.yml up -d postgres

# Apply migrations (Git Bash / WSL, or load env then run alembic by hand on Windows)
# Git Bash:
set -a; . ./infra/envs/backend.env; set +a
cd services/backend && uv run --extra api alembic upgrade head
```

Windows PowerShell equivalent for migrate / serve (load env, then run):

```powershell
Get-Content .\infra\envs\backend.env | ForEach-Object {
  $line = $_.Trim()
  if (-not $line -or $line.StartsWith('#')) { return }
  $i = $line.IndexOf('=')
  if ($i -lt 1) { return }
  Set-Item -Path ("Env:" + $line.Substring(0, $i).Trim()) -Value $line.Substring($i + 1).Trim()
}
$env:HERHEALTH_KNOWLEDGE_DIR = (Resolve-Path .\knowledge).Path
uv run --extra api --package herhealth-backend python -c "import asyncio; from alembic.config import main; main(['upgrade','head'])"
# Prefer: cd services/backend; uv run --extra api alembic upgrade head
```

### 3. Start retrieval (`:8001`) — required for every real turn

First load of `BAAI/bge-m3` can take **1–3 minutes**. Wait until `/health` is
ok before opening chat.

```powershell
# Terminal A — repo root
$env:HERHEALTH_INDEX_DIR = (Resolve-Path .\build\index).Path
uv run --package herhealth-model python -m herhealth_model
```

Check:

```powershell
curl.exe http://127.0.0.1:8001/health
# {"status":"ok"}
```

### 4. Start the backend (`:8000`)

```powershell
# Terminal B — repo root, same env-loading block as above, then:
$env:HERHEALTH_KNOWLEDGE_DIR = (Resolve-Path .\knowledge).Path
uv run --extra api --package herhealth-backend python -m herhealth_backend.app
```

Or with make (Git Bash): `make serve`

Check:

```powershell
curl.exe http://127.0.0.1:8000/health
# {"status":"ok"}
```

Restart the backend after any change to `HERHEALTH_VLLM_*` or
`HERHEALTH_MODEL_SELECTOR`.

### 5. Start the frontend (`:3000`)

```powershell
# Terminal C
cd services\frontend
npm install   # first time only
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) → sign up / sign in → set
date of birth if prompted (age band is injected into the triage prompt).

### 6. Test Base model

1. Open [http://localhost:3000/chat](http://localhost:3000/chat).
2. Start a **new** chat. If the model tabs appear, leave **Base** selected.
3. Send: *I've had irregular periods for three months.*
4. Expect clarifying questions or a conclude with an action code — with RAG
   citations and age context when DOB is on the account.

Without `HERHEALTH_MODEL_SELECTOR=on`, the Base / Fine-tuned tabs are hidden
and every turn uses OpenRouter.

### 7. Common failure: `502` + `WinError 10061`

```
triage dependency HTTP failure: [WinError 10061] No connection could be made...
POST /triage/turn → 502
```

That is almost always **`:8001` not listening**, not campus vLLM. Confirm
`curl http://127.0.0.1:8001/health`, then retry. Campus can be up
(`/v1/models` 200 on Lobot) while this laptop still 502s.

---

## Fine-tuned model (campus VM + laptop)

The Fine-tuned tab calls the same RAG + system prompt + age-band injection as
Base; only the reasoning HTTP client changes (campus LoRA `herhealth`).

**Hugging Face artifact (project fine-tune):**
[`herhealthgpt/qwen3.5-9b-herhealth-enfrar-lora-v2`](https://huggingface.co/herhealthgpt/qwen3.5-9b-herhealth-enfrar-lora-v2)
— private QLoRA on [`Qwen/Qwen3.5-9B`](https://huggingface.co/Qwen/Qwen3.5-9B).
On campus we serve a local checkout at
`/home/jovyan/models/herhealth-lora-v2` under the vLLM module name `herhealth`
(`HERHEALTH_VLLM_MODEL=herhealth`).

**The adapter is experimental / phrasing-trained.** It was not trained on
clarifying-question turns and must not be treated as a reviewed triage
decision-maker. See ADR 0011 / ADR 0016. The UI shows an unreviewed-model
warning.

Full detail: [`docs/runbooks/uni-server-vllm.md`](docs/runbooks/uni-server-vllm.md).

Hub for this project: [https://lobot.cs.queensu.ca](https://lobot.cs.queensu.ca)
· user `group-digi2026-g1`.

### A. On the university Jupyter VM (Lobot)

Closing JupyterLab (or Hub → Stop My Server) **kills the container** and vLLM.
Keep a Lab tab open while testing.

| | |
|---|---|
| Base | [`Qwen/Qwen3.5-9B`](https://huggingface.co/Qwen/Qwen3.5-9B) |
| Fine-tune (HF) | [`herhealthgpt/qwen3.5-9b-herhealth-enfrar-lora-v2`](https://huggingface.co/herhealthgpt/qwen3.5-9b-herhealth-enfrar-lora-v2) |
| Adapter id (vLLM / env) | `herhealth` |
| Adapter path on VM | `/home/jovyan/models/herhealth-lora-v2` |
| Venv | `~/herhealthgpt-venv` (fallback `~/vllm-env`) |
| Port **inside the pod** | **8000** |
| Pod IP `10.244.x.x` | **Not reachable from the laptop** |

**1. Clean** (JupyterLab → Terminal):

```bash
pkill -9 -f 'vllm serve' || true
pkill -9 -f 'VLLM::' || true
sleep 3
nvidia-smi --query-gpu=index,memory.used --format=csv
# expect ~0 MiB on both GPUs
```

**2. Start** (verified **2026-09-09**, vLLM 0.28.0 — engine init 15.98 s):

```bash
source ~/herhealthgpt-venv/bin/activate
# if that fails: source ~/vllm-env/bin/activate

rm -rf ~/.cache/vllm          # stale GPU P2P probe — see the runbook §0.1

nohup env \
  NCCL_P2P_DISABLE=1 \
  NCCL_IB_DISABLE=1 \
  VLLM_USE_FLASHINFER_SAMPLER=0 \
  NCCL_DEBUG=INFO \
  TRITON_CACHE_DIR=/home/jovyan/.cache/triton \
  HF_HOME=/home/jovyan/.cache/huggingface \
  vllm serve Qwen/Qwen3.5-9B \
  --enable-lora \
  --lora-modules herhealth=/home/jovyan/models/herhealth-lora-v2 \
  --max-lora-rank 16 \
  --max-model-len 8192 \
  --tensor-parallel-size 2 \
  --disable-custom-all-reduce \
  --enforce-eager \
  --limit-mm-per-prompt '{"image":0,"video":0}' \
  --host 127.0.0.1 --port 8000 \
  > /home/jovyan/vllm.log 2>&1 &
echo $! > /home/jovyan/vllm.pid
tail -f /home/jovyan/vllm.log
```

| Flag / env | Why |
|---|---|
| **`--disable-custom-all-reduce`** | **Mandatory.** Without it TP all-reduce corrupts activations → NaN logits → the sampler emits token 0 (`!`) forever, giving `!!!!!!!` answers, and startup deadlocks. Full write-up: runbook §0.1. |
| `NCCL_P2P_DISABLE=1` / `NCCL_IB_DISABLE=1` | Without them, TP=2 hangs after NCCL init |
| `VLLM_USE_FLASHINFER_SAMPLER=0` | FlashInfer JIT needs `curand.h` (missing on the image) |
| `--enforce-eager` | Avoids CUDA-graph / Inductor spin at empty VRAM |
| `--limit-mm-per-prompt '{"image":0,"video":0}'` | **Both** keys — the base is a multimodal hybrid, not a text model (runbook §0.2) |
| `--tensor-parallel-size 2` | 17.98 GiB of bf16 weights do not fit one 14.6 GiB A16 |
| `--max-model-len 8192` | The triage prompt is ~3,200–3,600 tokens before retrieval; 4096 leaves no room to generate (runbook §0.3) |
| `TRITON_CACHE_DIR` under `/home/jovyan` | Survives culls |

Wait for **`Application startup complete.`** (~30 s). Hundreds of `no matching
PunicaWrapper ... will be ignored` warnings on the way are expected — that is
vLLM skipping LoRA on the vision tower. Ctrl+C stops `tail` only.

First-time install after a wipe:

```bash
bash scripts/setup-uni-vllm.sh --clean
bash scripts/setup-uni-vllm.sh
bash scripts/setup-uni-vllm.sh --check
```

**3. Smoke-test on the VM:**

```bash
curl -s http://127.0.0.1:8000/v1/models
# must list Qwen/Qwen3.5-9B and herhealth

curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "herhealth",
    "messages": [{"role": "user", "content": "I have irregular periods and some pelvic pain, what could this mean?"}],
    "max_tokens": 4000,
    "chat_template_kwargs": {"enable_thinking": false}
  }'
```

Always send `chat_template_kwargs: {"enable_thinking": false}` (the backend
already does). Cloudflare quick tunnels are often **blocked** from this
cluster (`api.trycloudflare.com` timeout) — use the Jupyter proxy below.

### B. Reach campus from the laptop (Jupyter proxy)

`jupyter_server_proxy` is enabled on Lobot. From the **pod** terminal:

```bash
echo "len=${#JUPYTERHUB_API_TOKEN}"
curl -sS -H "Authorization: token ${JUPYTERHUB_API_TOKEN}" \
  "https://lobot.cs.queensu.ca/user/group-digi2026-g1/proxy/8000/v1/models"
```

Expect JSON listing `herhealth`. Copy the token:

```bash
echo "$JUPYTERHUB_API_TOKEN"
```

Put it in laptop `HERHEALTH_VLLM_API_KEY`. That token **rotates when the
Jupyter server restarts** — after a cull, copy a fresh one and restart the
backend.

From the **laptop** (PowerShell), after `backend.env` is filled:

```powershell
# Load HERHEALTH_VLLM_* from backend.env, then:
curl.exe -sS -H "Authorization: Bearer $env:HERHEALTH_VLLM_API_KEY" `
  "$env:HERHEALTH_VLLM_URL/v1/models"
```

Both `Bearer` and `token` schemes work against Lobot.

### C. Wire the laptop and test the Fine-tuned tab

1. Confirm local `:8001`, `:8000`, `:3000` are up ([above](#run-the-full-app-local-laptop)).
2. Set `HERHEALTH_MODEL_SELECTOR=on` and the three `HERHEALTH_VLLM_*` values.
3. Restart the backend so it rebuilds the model list.
4. Open [http://localhost:3000/chat](http://localhost:3000/chat) → **new** chat.
5. Click **Fine-tuned** (disabled until vLLM URL is configured and the backend
   restarted). Tabs lock after the first user message in a session.
6. Send a short symptom message. Expect the unreviewed-model notice, then a
   turn that still used local RAG + age band, with reasoning from campus.

If Fine-tuned stays greyed out: hard-refresh so `GET /triage/models` reloads.
If you get `502` / `10061`: fix `:8001` first.

**If RAG succeeds but chat returns `504 Gateway Time-out` on the Lobot proxy**
(backend log shows `POST …/proxy/8000/v1/chat/completions` → 504, UI says
*"A service we rely on is temporarily unavailable"*): local retrieval is fine;
the Hub/nginx proxy cut the request at ~60s while campus vLLM was still
generating (often first LoRA Triton JIT). Warm inside the pod first (below).

**If the Fine-tuned tab answers with `!!!!!!!!!!!`** (or the VM never binds
`:8000` and the log repeats `No available shared memory broadcast block found
in 60 seconds`): both are the same bug — vLLM's custom all-reduce running over
the broken GPU-to-GPU link on these A16s, corrupting activations until the
logits are NaN and the sampler emits token 0, which is `!` in Qwen's
vocabulary. Fix: `--disable-custom-all-reduce` and `rm -rf ~/.cache/vllm`,
both already in the step 2 command above. Confirm the log line reads
`Using ['PYNCCL'] all-reduce backends` with no `CUSTOM`. Diagnosed and fixed
2026-09-09; full write-up in the runbook §0.1.

**If the VM returns `EngineCore encountered an issue` / worker dies with
`apply_token_bitmask_inplace` / `CUDA: unspecified launch failure`:** the
engine is dead — restart vLLM. That crash was triggered by
`response_format: json_object` (xgrammar structured outputs). The laptop
backend no longer sends that field to Fine-tuned / vLLM; restart the local
backend after pulling that fix, then warm and retry.

On the **Jupyter terminal**, after a fresh serve is up, warm LoRA **without**
`response_format`:

```bash
time curl -s http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "herhealth",
    "messages": [{"role": "user", "content": "Say hello in one short sentence."}],
    "max_tokens": 64,
    "chat_template_kwargs": {"enable_thinking": false}
  }'
```

Wait until it returns (may take 1–3 minutes the first time). Run it once more —
the second should be much faster — then retry Fine-tuned from the laptop.

Other hosts (friend PC, vast.ai): see
[`friend-pc-vllm-setup.md`](docs/runbooks/friend-pc-vllm-setup.md) and
[`dev-vllm-lora-endpoint.md`](docs/runbooks/dev-vllm-lora-endpoint.md).

---

## Commands

| Command | Does |
|---|---|
| `make install` | `uv sync` — create or refresh `.venv` from the lockfile |
| `make validate` | check `knowledge/` against the contracts schemas |
| `make test` | pytest |
| `make lint` | ruff both packages, mypy strict on `packages/contracts/` |
| `make fmt` | ruff format and autofix |
| `make migrate` | apply Alembic migrations using `infra/envs/backend.env` |
| `make serve` | run the backend API on `127.0.0.1:8000` |
| `make build` | fetch → clean → chunk → `build/passages.parquet` *(phase 4)* |
| `make eval` | run the controller over the benchmark cases *(phase 3)* |
| `make lock` | re-resolve `uv.lock` after a dependency change |
| `make sync-check` | fail if `uv.lock` has drifted |

`make` is not installed by default on Windows — `winget install
ezwinports.make`, or run the PowerShell steps in
[Run the full app](#run-the-full-app-local-laptop).

---
## CI

Every workflow is **path-filtered**. A frontend change must not rebuild the model
image. When adding a workflow, the `paths:` key is mandatory.

---

## Evaluation

Reuses an existing 540-case-per-language benchmark with matched register variants
and labels for concern category, risk level, recommended action and clarification
need. **Labels are silver, not clinician-adjudicated. Say so wherever reported.**

Risk labels are derived once from the English source text and propagated to other
languages by `canonical_case_id`. **Never run English keyword rules on translated
text** — that produced language-asymmetric labels skewed toward routine.

**Blocks merge:** red-flag recall (must be 100%), per-language under-triage,
clarification recall on ambiguous cases, grounding, cross-language action
agreement. **Reported but not gated:** over-triage, average questions asked.

---

## Roadmap

| Phase | Work | State |
|---|---|---|
| **1** | Scaffold, contracts schemas, seed knowledge for three conditions, validators | in progress |
| **2** | Reasoning core — `update`, `should_stop`, `next_question`; unit tests for every stopping branch; scripted-dialogue CLI, no model in the loop | next |
| **3** | Evaluation — simulated patient, under/over-triage, clarification recall and specificity, average questions, questions that changed nothing | |
| **4** | Ingestion — one client per source, escalation criteria extracted first, `make fetch clean build` reproducing `passages.parquet` with a stable hash | |

Phase order is deliberate. Elimination is evaluated on three hand-written
conditions **before** anything is ingested. If it does not work at three
conditions, ten thousand scraped passages will not fix it.

---

## Language scope

Probe text is authored in **English only** for now. The serving model is
multilingual and renders questions at response time. The schema leaves room for
authored `fr` and `ar_eg` probes without migration.

**Known consequence, recorded deliberately:** deferring authored probes means
question wording in French and Arabic is model-generated rather than reviewed.
The benchmark above found severe language-specific regressions in non-English
output, so a sample of generated probes in both languages is reviewed for drift
before Phase 2 ships. When the authored Egyptian Arabic layer lands it will be
written by a native speaker — never machine translated.

---

## Safety, privacy and licensing

- **Not a diagnostic device, and not a substitute for clinical assessment.**
- **Escalation is deterministic.** Red flags are plain conditionals evaluated
  before any model call and cannot be overridden by a model.
- **Bias toward escalation.** Where a judgement call trades false alarms against
  missed escalations, the false alarm wins, and the reason is recorded in the
  row's `note`.
- **No invented numbers.** No probability, likelihood ratio, prevalence figure or
  confidence score appears anywhere in the knowledge base.
- **Source-traceable, not clinician-adjudicated.** See
  [Verification protocol](#verification-protocol) and `DATASHEET.md`.
- **Licence recorded per source.** The repository stays private.
- **Secrets never enter the repository.** `*.env` is gitignored;
  `infra/envs/*.env.example` documents required keys with empty values.

---

## Further reading

- [`CLAUDE.md`](CLAUDE.md) — the project spec. Binding.
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — environment setup, workflow, branching
- [`knowledge/README.md`](knowledge/README.md) — the seven files in detail
- [`docs/runbooks/`](docs/runbooks/) — standing up the model endpoint, SES,
  Google OAuth
- [`.claude/skills/`](.claude/skills/) — binding constraints on clinical
  authoring, repo conventions and source ingestion
