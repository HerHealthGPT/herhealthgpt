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
All seven knowledge files are authored and validated: 37 features, 12
conditions, 89 evidence rows, 14 red-flag rules, 5 sources, **103/103 quotes
verified verbatim** against their cited source. The stopping controller and the
evaluation harness are built and tested (380 tests).

**Not built yet:** retrieval, model serving, API, frontend. See
[`docs/ROADMAP.md`](docs/ROADMAP.md).

### Start here

| If you want to… | Read |
|---|---|
| Understand how the reasoning works, **with diagrams** | [`docs/KNOWLEDGE_BASE.md`](docs/KNOWLEDGE_BASE.md) |
| Find your way around the repository | [`docs/REPO_MAP.md`](docs/REPO_MAP.md) |
| Know what we are doing now and next | [`docs/ROADMAP.md`](docs/ROADMAP.md) |
| Read every module in detail | [`docs/CODE_GUIDE.md`](docs/CODE_GUIDE.md) |
| Know why a decision was made | [`docs/adr/`](docs/adr/) |

See a consultation run in 30 seconds:

```bash
make install
make triage CASE=services/backend/cases/sudden_severe_pain.yaml
```

---

## Table of contents

- [Why it is built this way](#why-it-is-built-this-way)
- [How it reasons](#how-it-reasons)
- [Architecture](#architecture)
- [Repository layout](#repository-layout)
- [The knowledge model](#the-knowledge-model)
- [Verification protocol](#verification-protocol)
- [Sources](#sources)
- [Quickstart](#quickstart)
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

**No model weights load inside the backend process.** Embeddings and reranking
are HTTP calls to `services/model`.

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

Install [uv](https://docs.astral.sh/uv/). Nothing else — not even Python.

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
```

That is the entire setup. `uv sync` reads `.python-version`, downloads CPython
3.12 if the machine lacks it, creates `.venv/`, and installs the exact versions
in `uv.lock` — including both local packages in editable mode. No activation
needed; `uv run` and every `make` target sync first.

**`uv.lock` is committed and is the source of truth.** CI runs `uv sync
--locked`, which fails rather than silently re-resolving.

---

## Commands

| Command | Does |
|---|---|
| `make install` | `uv sync` — create or refresh `.venv` from the lockfile |
| `make validate` | check `knowledge/` against the contracts schemas |
| `make test` | pytest |
| `make lint` | ruff both packages, mypy strict on `packages/contracts/` |
| `make fmt` | ruff format and autofix |
| `make build` | fetch → clean → chunk → `build/passages.parquet` *(phase 4)* |
| `make eval` | run the controller over the benchmark cases *(phase 3)* |
| `make lock` | re-resolve `uv.lock` after a dependency change |
| `make sync-check` | fail if `uv.lock` has drifted |

`make` is not installed by default on Windows — `winget install
ezwinports.make`, or read the one-line recipe out of the `Makefile`.

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
- [`.claude/skills/`](.claude/skills/) — binding constraints on clinical
  authoring, repo conventions and source ingestion
