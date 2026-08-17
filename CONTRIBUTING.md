# Contributing to HerHealthGPT

## What this system is

Urgency triage and informational guidance. It does not diagnose, and no file,
comment, docstring, string literal or commit message in this repo may describe it
as doing so. If you find wording that implies diagnosis, that is a bug — fix it.

---

## Environment setup

Reproducibility here means three things are pinned, not one: the Python version,
the exact transitive dependency set, and how the local packages link to each
other. `uv` pins all three. A plain `venv` plus `pip install -e` pins none of them,
which is why we do not use one.

### One-time, per machine

Install [uv](https://docs.astral.sh/uv/). Nothing else — not even Python.

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows PowerShell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### Per clone

```bash
git clone <repo> && cd herhealthgpt
uv sync
```

That is the whole setup. `uv sync` reads `.python-version`, downloads CPython
3.12 if the machine does not have it, creates `.venv/`, and installs the exact
versions recorded in `uv.lock` — including both local packages
(`packages/contracts` and `services/data`) in editable mode.

You do **not** need to activate the virtualenv. `uv run <command>` and every
`make` target resolve it automatically and re-sync first, so you cannot
accidentally run against a stale environment. If you prefer an activated shell
for your editor, `.venv/Scripts/activate` (Windows) or `source .venv/bin/activate`
(macOS/Linux) works normally.

### Point your editor at it

Select the interpreter at `.venv/Scripts/python.exe` (Windows) or
`.venv/bin/python` (macOS/Linux). In VS Code: **Python: Select Interpreter**.

---

## Daily commands

Run from the repo root.

| Command | Does |
|---|---|
| `make install` | `uv sync` — create/refresh `.venv` from the lockfile |
| `make validate` | check `knowledge/` against the schemas in `packages/contracts/` |
| `make test` | pytest |
| `make lint` | ruff across both packages, plus mypy strict on `packages/contracts/` |
| `make fmt` | ruff format and autofix |
| `make build` | fetch → clean → chunk → `build/passages.parquet` *(phase 4)* |
| `make eval` | run the triage controller over the benchmark cases *(phase 3)* |
| `make lock` | re-resolve `uv.lock` after a dependency change |
| `make sync-check` | fail if `uv.lock` has drifted from the pyproject files |

`make` is not installed by default on Windows. Either install it
(`winget install ezwinports.make`, or use Git Bash) or read the recipe out of the
`Makefile` — every target is one command.

---

## The lockfile

**`uv.lock` is committed and it is the source of truth for the environment.**
Never edit it by hand and never delete it to "fix" a resolution problem.

CI runs `uv sync --locked`, which fails rather than silently re-resolving. So if
the lockfile and the `pyproject.toml` files disagree, CI goes red instead of
quietly building against different versions than you have locally. That failure
mode is the entire point of the setup — do not paper over it.

### Adding or changing a dependency

1. Edit the `dependencies` list in the right `pyproject.toml`:
   - shared schema/runtime dep → `packages/contracts/pyproject.toml`
   - data service runtime dep → `services/data/pyproject.toml`
   - fetch/parse/parquet dep → the `ingest` extra in `services/data/pyproject.toml`,
     so `make validate` does not drag in pyarrow
   - test/lint tooling → the `dev` group in the **root** `pyproject.toml`
2. `make lock`
3. Commit `pyproject.toml` **and** `uv.lock` in the same commit. A lockfile change
   arriving separately from the dependency change is how teammates end up on
   different versions.

### When someone else changes the lockfile

`git pull` then `uv sync`. Or just run any `make` target — they all sync first.

---

## Repo layout

```
services/frontend/    Next.js PWA
services/backend/     FastAPI: triage, tracker, retrieval, safety, orchestration
services/model/       vLLM: Qwen3.5-9B, embeddings, reranker
services/data/        ingestion, evaluation harness, benchmark cases
packages/contracts/   Pydantic schemas, error codes, safety policy
packages/types-ts/    TypeScript types generated from OpenAPI
knowledge/            features.yaml conditions.yaml evidence.csv red_flags.yaml
                      sources.yaml weights.yaml actions.yaml
infra/                compose.yml, envs/*.env, Caddy, Prometheus
.github/workflows/    path-filtered CI
```

### The import rule

Nothing outside `packages/contracts/` may be imported across a service boundary.
If a service needs something from another service, either the thing belongs in
contracts or the boundary is drawn in the wrong place. This will be enforced by
import-linter in CI once a second Python service exists.

### CI

Every workflow is path-filtered. A frontend change must not rebuild the model
image. When you add a workflow, add the `paths:` key — no exceptions.

---

## Working on `knowledge/`

Read [`.claude/skills/clinical-data-authoring/SKILL.md`](.claude/skills/clinical-data-authoring/SKILL.md)
first; the constraints there are binding on humans and agents alike. The short
version:

- Evidence strength is a five-level ordinal scale — `strong_support`,
  `weak_support`, `neutral`, `argues_against`, `rules_out` — and nothing else.
  `neutral` is expressed by **omitting the row**. `evidence.csv` is sparse.
- Four action codes: `SELF_CARE`, `ROUTINE_APPOINTMENT`, `URGENT_SAME_DAY`,
  `EMERGENCY`. Locale-specific instructions ("call 111", "see your GP") never
  appear in a knowledge file or a passage — they are resolved per locale at
  response time.
- Never invent a probability, a prevalence figure or a citation. Every clinical
  row carries a `source_id` resolving to a real fetched document. No source, no
  row.
- Never write an ICD-11 code from memory. Write `TODO_VERIFY` and let the WHO ICD
  API lookup fill it.
- When a choice trades false alarms against missed escalations, choose false
  alarms and record why in the row's `note`.
- For every symptom a source lists under a condition, also ask whether its
  *absence* would make you doubt the condition. If yes, add the `argues_against`
  row too. This is what makes elimination work and it is the step most often
  forgotten.

Clinician sign-off is out of scope for this project. The citation trail is what
stands in for it, which is why `source_id` is mandatory. Results computed from
this dataset are silver annotations, not clinician-adjudicated, and should be
labelled that way wherever they are reported.

Probe text is authored in English only for now. The serving model is multilingual
and renders questions at response time.

---

## Fetching source content

Read [`.claude/skills/source-ingestion/SKILL.md`](.claude/skills/source-ingestion/SKILL.md).

- Raw fetched content is immutable. It lands in `raw/{source}/{YYYY-MM-DD}/` and
  is never overwritten; a re-fetch creates a new dated directory so changes are
  diffable. Every record stores `url`, `fetched_at`, `content_hash` and `licence`.
- Confirm before any network call. Cache aggressively. **Ingestion and triage
  tests never hit the network**, and run with `make test`. (The backend's app
  layer adds database tests that start a local PostgreSQL in Docker — no external
  network — fenced into a separate `make test-api` suite.)
- Source precedence, lower wins on conflict: NICE CKS → NHS → NICHD/MedlinePlus →
  CDC → RCOG/ACOG. When two sources disagree on urgency the higher-precedence one
  wins **and** the conflict is appended to `build/conflicts.jsonl`. Never resolve
  silently.

---

## Secrets

`raw/`, `build/` and `*.env` are gitignored; `*.env.example` is tracked.

Copy `infra/envs/data.env.example` to `infra/envs/data.env` and fill in your own
keys. No key, token or secret is ever committed, pasted into an issue, or written
into a knowledge file. If a credential does reach the repo or a chat log, rotate
it — do not just delete the line.

---

## Branching strategy

**Trunk-based development with short-lived branches.** There is no `develop`
branch and no release branch. Git-flow is ruled out by the two-day branch limit —
a model with long-lived parallel integration branches cannot coexist with
branches that live under two days, and trying to run both gives you the merge
pain of one and the benefits of neither.

### `main` is the only long-lived branch

It is always green and always deployable. Nothing is committed to it directly;
everything arrives by pull request with CI passing.

Protect it on the remote:

- require a pull request before merging
- require the `data` status check to pass
- require branches to be up to date before merging
- disallow force pushes and deletion

### Branch naming

`<type>/<scope>-<short-slug>` — the same `type` and `scope` vocabulary as the
commit convention, so a branch name predicts its commits.

```
feat/data-nhs-content-client
feat/knowledge-pcos-evidence-rows
fix/backend-selfcare-stop-threshold
chore/repo-pin-uv-lockfile
docs/repo-contributing-branching
```

**Types:** `feat`, `fix`, `refactor`, `test`, `docs`, `chore`
**Scopes:** `data`, `knowledge`, `contracts`, `backend`, `frontend`, `model`,
`infra`, `repo`

Scopes match top-level directories, which is also what the CI path filters and
`CODEOWNERS` key off. A branch whose changes span more than one scope is usually
two branches.

### Lifetime: under two days

Not a style preference. A branch open for a week is a branch that will conflict
with the knowledge files, the lockfile, or both. If work will take longer than
two days, split it: land the schema, then the data, then the consumer. Each
should be independently reviewable and leave `main` green.

Prefer merging something incomplete but inert — a module nothing imports yet, a
knowledge file nothing reads yet — over holding a large branch open.

### Keeping a branch current

**Rebase onto `main`, do not merge `main` into your branch.** Branches this short
should have linear history.

```bash
git fetch origin
git rebase origin/main
```

### Landing

**Squash merge**, with the squash commit message following the conventional
format. One branch becomes one commit on `main`, so `main`'s history reads as a
list of changes rather than a list of merges — and any single change can be
reverted with one `git revert`.

Delete the branch after merge.

### Two rules specific to this repo

**1. Knowledge changes never share a pull request with code changes.**

A branch touching `knowledge/` touches only `knowledge/`. The reason is
revertability: if an evidence row or a red-flag threshold turns out to be wrong,
you need to revert exactly that row without also reverting the parser, the
validator or the API change that shipped alongside it. Clinical data and the code
that reads it move on separate branches and land as separate commits.

The same applies in the other direction — a schema change in
`packages/contracts/` that requires knowledge edits lands first, backward
compatible, then the knowledge branch follows.

**2. `pyproject.toml` and `uv.lock` always move together.**

Never commit a dependency change without the regenerated lockfile in the same
commit. A lockfile arriving in a later commit is how teammates end up on
different versions.

If `uv.lock` conflicts during a rebase, **do not resolve it by hand** — the file
is generated and hand-merging it produces a lockfile matching neither side:

```bash
git checkout --theirs uv.lock   # take main's version
uv lock                          # regenerate from the merged pyprojects
git add uv.lock
git rebase --continue
```

### Releases

Tag on `main`, semver, annotated:

```bash
git tag -a v0.2.0 -m "phase 2: reasoning core"
git push origin v0.2.0
```

Phase milestones get a tag so an evaluation result can always be traced to the
exact knowledge base and controller that produced it. This matters for Phase 3 —
a reported under-triage number is meaningless without the commit it was measured
at.

### Hotfixes

No separate flow. A `fix/` branch off `main`, squash merged, tagged if it needs
to be. Trunk-based development means the fix path and the feature path are the
same path — which is the point, because a rarely-exercised emergency process is
the one that fails in an emergency.

### Review routing

`CODEOWNERS` is per folder, not per repo. Check it before editing outside your
area.

---

## Commits

Conventional commits, scoped to the area — same vocabulary as branch names:

```
feat(data): add NHS content client
fix(knowledge): correct endometriosis red-flag threshold
chore(repo): pin uv lockfile
docs(repo): document branching strategy
```

Write the body when the *why* is not obvious from the diff. For a knowledge
change, name the source that justifies it.

Prefer boring, readable code; this is read by people, not scaled to millions of
requests.
