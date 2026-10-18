---
status: proposed
---

# Cycle data is imported from any tracker, and fresh data may pre-fill answers

> **Proposed, not accepted.** An in-session product decision, 2026-10-17,
> taken with the person building the app rather than at supervisor or mentor
> review — the same gate [ADR 0015](0015-a-user-may-keep-a-date-of-birth-and-a-health-note.md)
> named for itself. It goes further than ADR 0015 in one respect that a
> reviewer should read first: stored data is allowed to **answer features**,
> not only to sit in the prompt as background. See the risk register.

## Context

The Accounts glossary ([`services/backend/CONTEXT.md`](../../services/backend/CONTEXT.md))
has defined **Cycle data** since the glossary was written — *"Menstrual
tracking a user may import to give the system context. Hers, optional, and
deletable independently of her account."* — and
[`docs/ROADMAP.md`](../ROADMAP.md) lists the import as post-MVP work. Nothing
implements it.

The product goal is stated plainly: **a woman who has months of tracker data
should not be asked, question by question, for what that data already shows.**
Every repeated question is a turn, a model call and the tokens for one, spent
on something she has already recorded. `cycle_regularity`, `cycle_length` and
`period_duration` are among the first features any menstrual consultation
reaches, and a tracker measures them better than her recall does.

Four facts shape the design:

1. **Users will upload from any application.** Clue, Flo, Apple Health,
   Samsung Health, Fitbit and others export different shapes — CSV, JSON, XML,
   a zip of XML, or a PDF "report for your doctor". No fixed list of
   converters covers "any".
2. **The system can only reason over `features.yaml`.** A tracker field that
   maps to no feature cannot change a decision; extracting it adds privacy
   cost and no benefit.
3. **Many of the features a tracker informs are red-flag clauses.**
   `bleeding_heaviness`, `bleeding_between_periods`, `periods_stopped_duration`,
   `pregnancy_status` and `pelvic_pain_severity` all appear in
   `red_flags.yaml`. A pre-filled benign value on any of them removes the
   question that would have fired an escalation.
4. **The knowledge base defines some values only in words.** `cycle_length`'s
   buckets carry their thresholds in their names (`under_21_days`,
   `21_to_35_days`, `over_35_days`), so a computed length maps onto them
   mechanically. `cycle_regularity: irregular` and `cycle_length:
   varies_widely` carry no threshold anywhere in `knowledge/`. Choosing one —
   "more than N days of variation is irregular" — would be an independent
   clinical judgement, which the [verification protocol](../../CLAUDE.md#verification-protocol-replaces-clinician-review)
   forbids.

## Decision

### 1. The whole file is uploaded and the backend extracts from it

From both the chat composer's attach button and Settings; one endpoint, one
flow, the result saved to her account.

- **Known formats are parsed by code**: a converter per format, starting with
  a CSV template of our own and Apple Health's `export.xml`, then each app for
  which a real (anonymised) sample export exists. No converter is written from
  a guessed format.
- **Anything else is extracted by the base model** (`Qwen/Qwen3.5-9B`, the
  same vLLM process that decides triage — [ADR 0018](0018-local-models-decide-and-the-adapter-answers.md)),
  under guided decoding into a schema whose only representable values are
  `features.yaml` ids and their `allowed_values`, plus dates. This is the same
  defence `TriageDecision` relies on: the file can contain anything, including
  text written to look like instructions, and the output can still only be a
  closed-vocabulary value.
- **The raw file is never stored.** It is held in a temporary file for the
  length of the request, deleted in a `finally`, and never logged — not its
  content, not its name.
- **Parsing is defensive by construction**: an upload size cap, XML through
  `defusedxml` with streaming `iterparse` (Apple exports run to hundreds of
  MB), a decompressed-size cap on zips, and a hard timeout on model
  extraction.
- **Production has no model route yet** (CLAUDE.md, "Deploy"), so model
  extraction reports "not configured" there exactly as triage does; code
  converters work regardless.

### 2. What is extracted, and what is discarded

Extracted: only what maps onto a feature — period days and flow, spotting
between periods, logged pain and its intensity, discharge as the app labels
it, bloating, nausea, back pain, fatigue, mood, skin, weight entries, and
pregnancy test results.

**Discarded at parse time, even when present:**

- **Free-text notes.** No text from the file ever reaches the triage prompt.
  Only closed-vocabulary values and dates do.
- **Sexual activity and contraception logs.** Highly sensitive on a service
  whose users may share a device with someone who should not see them, and
  no feature reads them.
- Location, heart rate, sleep, workouts and every other non-menstrual record.

### 3. Before anything is saved, she confirms what was found

The import returns a preview — "14 periods, January to October 2026; cycles
of 38–45 days; cramps logged before your period in 5 of 6 cycles" — and
nothing is written until she accepts it. This is the only check on model
extraction's accuracy, and it is mandatory, not a convenience.

### 4. Fresh data pre-fills answers; stale data makes the model ask

A tracker-derived value enters the case vector as an **answered feature** —
the same mechanism that seeds `age_band` from her date of birth in
`app/triage/routes.py` — when all of these hold:

| Condition | Why |
|---|---|
| Her last logged entry is within the freshness window (default **45 days**) | One full cycle at the long end of `21_to_35_days`, with margin. Older data may describe a pattern that has since changed. |
| Cycle-pattern values rest on at least **3 complete cycles** | One cycle is not a pattern. |
| The value maps onto `allowed_values` mechanically | `cycle_length` only when every logged cycle falls in the **same** bucket; `period_duration` likewise. Values defined only in words (`irregular`, `varies_widely`) are **never** pre-filled until a cited source defines them. |
| The value comes from something she logged, never from an absence | "No cramps logged" is not `pelvic_pain_timing: none`. Not logging is not the same as not happening — the `argues_against` discipline, applied here. |
| **The feature appears in no clause of `red_flags.yaml`** | See below. Computed from the file at load time, never listed by hand. |
| Nothing she has said in this consultation contradicts it | Her own words today always win, as they already do over the profile age band. |

**The red-flag exclusion is the one place this ADR declines the request as
made.** Pre-filling was asked for wherever the data is recent. For features
that a red-flag clause reads, a pre-filled value either suppresses the
question that would have escalated (a benign value) or escalates on data
nobody confirmed today (an alarming one), and ADR 0015 already ruled that
stored data may not fire a red flag. CLAUDE.md binding consequence 3 settles
the trade: when false alarms and missed escalations conflict, choose false
alarms. So for those features the tracker data goes into the prompt as
background, and the model asks one short confirming question — "Your tracker
shows heavy flow on your last three periods — is it still like that?" — which
costs one turn rather than an open-ended exchange.

**Safety signals force a question.** A positive pregnancy test logged in the
freshness window, flow logged as the app's heaviest level, or bleeding
between periods, each requires the model to put the matching feature to her
before it may conclude.

Everything else the data shows, and everything that fails a condition above,
reaches the model as background through `render_known_background`, framed as
ADR 0015 frames the health note: from her tracking app, unverified, dated by
its last entry, and unable to fire a warning sign on its own.

### 5. Storage

A `cycle_entries` table — `user_id`, `date`, `feature_id`, `value`,
`source_app`, `imported_at` — holding closed-vocabulary values only, so the
table can hold nothing the vocabulary cannot express. `user_id` cascades on
account deletion. `GET` / `PUT` / `DELETE /accounts/cycle-data`, so it can be
deleted on its own, as the glossary requires. A re-import replaces the
previous one rather than merging, so there is never a question of which
import is current.

## What this does not change

- **`TriageDecision`**, the action codes, and the closed vocabularies. No new
  decision type, no new feature, no new condition.
- **Red flags stay derived from the consultation.** No stored value fires
  one.
- **"Never diagnoses."** The preview shows what was found in her data; it
  names no condition, and UI copy says "cycle data", never "history",
  "records" or "health data" (the glossary's _Avoid_ list).

## Risk register

- **This is the first time stored data answers a feature without her saying
  it in the consultation.** ADR 0015 seeded `age_band` the same way, but a
  date of birth is demographic. A cycle length is clinical. If the data is
  wrong — a missed log, two apps disagreeing, a model extraction error that
  slipped past her preview — the model reasons on it and does not ask. The
  freshness window, the three-cycle minimum and the preview are mitigations,
  not proof.
- **Pre-filled cycle features move the differential.** A wrong `cycle_length:
  21_to_35_days` weakens PCOS through the evidence grid with no question asked.
  `make eval`'s 540 cases carry no cycle data, so the benchmark can detect
  neither the token saving nor an anchoring error. Both are unmeasured.
- **The whole file passes through the server.** It is not stored, but for the
  length of a request the backend holds data far beyond what it keeps —
  everything an Apple Health export contains. Parsing in the browser would
  have avoided that; it was considered and declined because it cannot handle
  formats nobody has written a converter for, and "any application" was the
  requirement.
- **Model extraction from PDFs is unmeasured.** Its accuracy is unknown until
  it is run against real reports, and her confirmation is the only check.
- **`cycle_entries` is stored in plaintext**, inheriting the same unbuilt
  application-layer encryption ADR 0015 records for `health_notes.content`
  and `messages.content`. It widens what a leaked snapshot contains.
- **The freshness window and cycle minimum are product parameters, not
  sourced figures.** They are configuration, recorded here as chosen values,
  and must not be described as clinically derived.

## Migration checklist

1. This ADR, and the **Cycle data** glossary entry amended to match.
2. Contracts: the extraction schema, closed over `features.yaml`.
3. The tracker field map: per-format field → feature id and value, every
   target validated against `features.yaml` by a test; shown for review in
   batches of at most ten rows.
4. Triage: the summary (cycle lengths, period durations, per-cycle symptom
   counts), the pre-fill rule with its red-flag exclusion derived from
   `red_flags.yaml`, and the background wording, each pinned by tests.
5. Backend: migration `0011`, the model, the routes, the CSV and Apple Health
   converters, model extraction, temp-file handling, deletion tests.
6. Frontend: the attach button, the preview, the Settings section, EN/FR/AR
   strings, RTL.
7. Per-app converters as real sample exports arrive.
