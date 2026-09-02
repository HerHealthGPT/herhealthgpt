# Handoff — 2026-09-02

Written for the next agent session (Cursor). Repo state at the time of writing:
branch `frontend`, working tree clean, everything pushed. Delete this file once
its contents have been absorbed.

---

## Read these first, in this order

1. **`CLAUDE.md`** — binding. Not background, not style guidance. The rules in
   it override default behaviour.
2. **`CONTEXT-MAP.md`** — two bounded contexts, Triage and Accounts. The same
   word means different things across the boundary ("conversation" vs
   "consultation"). Read before naming anything.
3. **`docs/adr/0011-controller-free-triage.md`** — the current target
   architecture and the migration checklist that most remaining work sits on.

## Five rules that will bite you if you skip them

1. **Never invent medical content.** Every row in `evidence.csv` and
   `red_flags.yaml` must be a restatement of a sentence a cited source actually
   says, with that sentence copied verbatim into `source_quote` — a complete
   paragraph, no truncation, no fragments stitched across an ellipsis. No
   independent clinical judgement, by the team or by you, in a row *or in its
   note*. If a source does not say it, it does not go in. If two sources
   contradict each other, write no row in either direction and record why in a
   tracked file.
2. **Git is the user's job.** Never commit, branch, merge, or push. Leave work
   in the tree and say what changed.
3. **Ask before any network call.** Check `services/data/ingest.lock.jsonl`
   first — it records what was already fetched, so the ask can name exact URLs.
4. **Never produce more than 10 clinical rows without stopping for review.**
5. **The system never diagnoses.** No file, comment, docstring, string literal,
   commit message or UI copy may describe it as diagnosing.

## Traps that cost real time — do not rediscover these

- **`make verify-quotes` needs a complete `build/clean`, which is gitignored
  and absent on a fresh clone.** It reports `NOT_FOUND` for any row whose page
  is not cleaned locally — visually identical to a fabricated quote. On
  2026-09-02 it failed on 31 quotes purely for this reason (49 of 67 documents
  present). After re-fetching, all 156 verified. **Run `make fetch && make
  clean` before believing a failure.**
- **OpenRouter `response_format: {type: "json_schema", strict: true}` hangs
  indefinitely** — no error, no timeout, no response. Use
  `{"type": "json_object"}` plus an explicit shape instruction in the prompt.
- **There is an intermittent silent hang** in the triage turn: retrieval and
  OpenRouter both log 200 OK, then nothing — no response, no traceback, not
  even from an explicit `except Exception: logger.exception(...)`. It is
  *contained*, not fixed, by `asyncio.wait_for(REASONING_TIMEOUT_SECONDS=150)`
  in `services/backend/src/herhealth_backend/app/triage/routes.py`. Root cause
  still open.
- **`build/conflicts.jsonl` exists but is gitignored and written by no pipeline
  stage.** Anything recorded only there reaches no reviewer and dies on a fresh
  clone. Record conflicts in the tracked file's own `note`.
- **Do not count `evidence.csv` with `wc -l`.** `source_quote` and `note`
  contain embedded newlines. Parse it as CSV.
- Docker Desktop was down locally, so the ~11 testcontainers-backed backend
  tests under `services/backend/tests/app` could not run. `make test` skips
  them via `--ignore`.

## What landed on 2026-09-02

- **Citations end to end.** `RetrievedPassage.url` (resolved from
  `ingest.lock.jsonl` via `services/model/src/herhealth_model/source_urls.py`),
  `cited_passages` on the turn payload (`routes.py::_decision_payload`,
  resolved eagerly at the turn and persisted, because retrieval is a live
  similarity search), and `services/frontend/src/components/chat/cited-sources.tsx`
  rendering verbatim quotes with working links. Documented in ADR 0012.
- **ADR 0013 (status: `proposed`)** — `EMERGENCY` conclusions may name
  `matching_conditions` alongside `red_flag_id`. `URGENT_SAME_DAY` red flags
  keep the original restriction. Cancer stays unmodelled and unnameable.
  First tests `TriageDecision` ever had: `packages/contracts/tests/test_decision.py`.
- **Batch 24** — two new features (`discharge_smell`, `discharge_appearance`)
  and 5 rows. `evidence.csv` 135 → 140, `features.yaml` 37 → 39.
  Fixed a real defect: `bacterial_vaginosis`, `thrush` and
  `sexually_transmitted_infection` all shared one identical
  `abnormal_discharge: yes` row, so discharge over-triaged toward the infective
  reads and BV could never be raised. Note the rows are **machine-drafted and
  provenance-checked, not clinically reviewed** — the batch header says so.
- **Mariam's batches 17–23 verified clean.** All 156 quotes now verify verbatim.

## What to do next, in priority order

### 1. Issue #20 — ADR 0011 migration, items 5 and 7–9

This is the main remaining architecture work. Items 1–3 are done; 4 and 6 are
substantially done but via **OpenRouter rather than a self-hosted vLLM**, which
is why item 7 is blocked.

- **Item 7** — wire guided decoding to `TriageDecision.model_json_schema()`.
  Needs real vLLM; OpenRouter's schema mode hangs (above).
- **Item 8** — delete `engine.py`, `state.py`, and the `should_stop` path
  through `dialogue.py`. **Only after 4–7 are reviewed and working.** All three
  files are still in the tree by design.
- **Item 9** — `make eval` must **report** red-flag recall, not assert
  `== 1.0`. Once escalation depends on the model noticing injected
  `red_flags.yaml` text, 100% recall stops being provable and becomes a
  measured rate. `DATASHEET.md` needs a sentence saying so. Neither has
  happened.
- **Item 5** — retrain the QLoRA adapter on multi-turn data. Bootstrap data
  exists at `services/data/eval/benchmark/bootstrap_multi_turn.jsonl` (18
  conversations, bootstrap-only — real user prose still needed). **Until this
  ships and is reviewed the adapter is phrasing-only and must not choose an
  action code**; it was trained on `gold_seeds_styled.csv`, which contains no
  example where the right move is a clarifying question, and that is the
  documented cause of clarification collapsing to 0.000.

### 2. Issues #13 and #14 — Accounts

Read a past conversation again; delete a conversation and delete the account.
Both `ready-for-agent`. #5 is the parent epic.

### 3. Knowledge depth, not breadth

The next authoring pass should deepen the thinnest conditions, **not add new
ones**. A new condition with one row reproduces exactly the BV defect fixed in
batch 24. Thinnest now, at 3 rows each: `bacterial_vaginosis`, `infertility`,
`inherited_bleeding_disorder`, `iron_deficiency_anaemia`; then
`pelvic_organ_prolapse` (4).

Confirmed blocked by sourcing, re-checked 2026-08-19 — do not re-investigate
without a new source: hyperprolactinaemia, endometrial polyp, functional
hypothalamic amenorrhoea, pregnancy-related bleeding.

### 4. Issue #15 — AWS deploy, managed DB, no public access

### 5. Small cleanups

- **10 stale `build/conflicts.jsonl` references** still describe it as where
  conflicts are logged: `README.md`, `CONTRIBUTING.md`, `docs/CODE_GUIDE.md`,
  `knowledge/red_flags.yaml` (×2), `docs/adr/0004-*.md`,
  `packages/contracts/src/herhealth_contracts/knowledge.py`,
  `.claude/skills/source-ingestion/SKILL.md`,
  `services/data/evidence_batches/batch_10_*.yaml`. `CLAUDE.md` and
  `knowledge/features.yaml` were fixed on 2026-09-02; the rest were left
  deliberately, to avoid sprawling one change across the repo.
- **ADR 0013 is `proposed`** — needs supervisor/mentor review to accept.
- **`nhs/pregnancy_bleeding` fails to fetch.** No row cites it (the
  `bleeding_in_pregnancy` red flag cites womenshealth, which verifies), so it
  is not urgent — but the target is still declared in `ingest_targets.yaml`.

## Open question never resolved

Whether sign-up should collect an **age band** for model context. It would
genuinely help triage — `perimenopause` vs `pcos` vs
`primary_ovarian_insufficiency` separate substantially on age — but it is
personal data with real consequences for the privacy story and the DATASHEET.
No decision was made; no ticket was filed.

## Security

An OpenRouter API key was pasted in plaintext into a chat session on this
project. **Treat it as compromised and rotate it if that has not already been
done.** Rotation was advised at the time but never confirmed.

## Standing limitation to repeat wherever results are reported

The knowledge base is **source-traceable but not clinician-adjudicated**.
Benchmark labels are **silver**, not clinician-adjudicated. Never describe
either as clinically validated, expert-reviewed, or verified. Coverage gaps are
a stated limitation, not an oversight — report them wherever coverage is
reported.
