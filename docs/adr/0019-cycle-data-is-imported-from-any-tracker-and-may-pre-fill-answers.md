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
  asked for JSON in the shape of `CycleExtraction` (below), whose only
  representable values are closed-vocabulary tokens and dates. Its reply is
  parsed and validated against that schema exactly as a triage decision is
  (`triage/chain.py` — vLLM's `response_format` is not used, because it
  crashed the engine; README, "Fine-tuned model"). The file can contain
  anything, including text written to look like instructions, and what
  survives validation can still only be a closed-vocabulary value.
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
it, bloating, nausea, back pain, fatigue, mood, skin, and
pregnancy test results.

**Discarded at parse time, even when present:**

- **Free-text notes.** No text from the file ever reaches the triage prompt.
  Only closed-vocabulary values and dates do.
- **Sexual activity and contraception logs.** Highly sensitive on a service
  whose users may share a device with someone who should not see them, and
  no feature reads them.
- Weight, location, heart rate, sleep, workouts and every other non-menstrual record.

### 3. Before anything is saved, she confirms what was found

The import returns a preview — "14 periods, January to October 2026; cycles
of 38–45 days; cramps logged before your period in 5 of 6 cycles" — and
nothing is written until she accepts it. This is the only check on model
extraction's accuracy, and it is mandatory, not a convenience.

### 4. Fresh data pre-fills answers; stale data makes the model ask

A tracker-derived value enters the case vector as an **answered feature** —
the same mechanism that seeds `age_band` from her date of birth in
`app/triage/routes.py` — when every condition below holds. Anything she says
in the consultation overrides it, as her words already override the profile
age band.

**Freshness.** Her last logged entry must fall within **45 days**: the longest
cycle `features.yaml` treats as within range (`21_to_35_days`) plus a 10-day
margin. The 35 is the knowledge base's own bucket edge; the 10 is ours. A
cycle-pattern value must also rest on at least **3 complete cycles** — a
product parameter, not a sourced figure. Both are configuration, and must
never be described as clinically derived.

**Mapping onto `allowed_values`, value by value.** Every rule here is either
mechanical or quoted; none is a threshold the team chose.

| Feature | Pre-filled when | Authority |
|---|---|---|
| `cycle_length` | Every logged cycle falls in the same bucket | The buckets carry their thresholds in their names |
| `cycle_regularity: irregular` | Any logged cycle in the window is under 21 or over 35 days | NHS, already quoted in `evidence.csv` (`normal_variation` / `cycle_length`): *"A woman's periods are irregular if the gap between them is less than 21 days or more than 35 days."* |
| `cycle_regularity: regular` | Every logged cycle is 21–35 days | The complement of the same sentence, read the way that row's own note already reads it |
| `cycle_length: varies_widely` | **Never** | No source in `knowledge/` defines it |
| `period_duration` | Every logged period falls in the same bucket | Mechanical |
| Symptom features | She logged the symptom, or confirmed its absence (below) | Mechanical |

**Absence is never read as "no".** "No cramps logged" is not
`pelvic_pain_timing: none` — not logging is not the same as not happening,
the `argues_against` discipline applied here. Absence becomes usable only when
she says so herself: the import preview asks about the few features where it
matters most — *"We didn't find any pain logged in your last 6 cycles. Is that
because you don't get period pain?"* — and only "Yes, no pain" pre-fills a
value. That value is her own statement, made at upload, and expires with the
freshness window like any other.

**Red-flag features: pre-filled in the alarming direction only.** For a
feature some clause of `red_flags.yaml` reads — computed from the file at
load time, never listed by hand — the danger runs one way. A pre-filled
benign value (`bleeding_heaviness: light`, `pregnancy_status: not_pregnant`)
removes the question that would have escalated; a pre-filled alarming value
can only make an escalation more likely. CLAUDE.md binding consequence 3
settles that trade toward false alarms, so:

| The tracker shows, within the window | Pre-filled |
|---|---|
| Flow at the app's heaviest level | `bleeding_heaviness: heavy` |
| Bleeding between periods | `bleeding_between_periods: yes` |
| A positive pregnancy test | `pregnancy_status: possibly_pregnant` — never `pregnant`, which is a stronger claim than a home test |
| Anything benign — lighter flow, a negative test, no spotting | Nothing. Background only, and the model asks one short confirming question: *"Your tracker shows lighter periods lately — is that still how they are?"* |

**This partly reverses ADR 0015**, which ruled that stored data may never
fire a red flag. Here a stored value can supply one clause of a rule — and
no more than one, which holds only because of two rules stated here so they
cannot be relaxed by accident. Checked against `red_flags.yaml` on
2026-10-18, four rules read a feature the tracker can pre-fill:

| Rule | Clauses | Why a log alone cannot fire it |
|---|---|---|
| `pelvic_pain_with_heavy_bleeding` (EMERGENCY) | pain severity ≠ none, heaviness heavy | needs `pelvic_pain_severity` |
| `possible_ectopic_pregnancy` | periods stopped < 3 months, bleeding between periods, pain severity ≠ none | needs `pelvic_pain_severity` |
| `pelvic_pain_in_pregnancy` | pain severity ≠ none, pregnant or possibly pregnant | needs `pelvic_pain_severity` |
| `bleeding_in_pregnancy` | pregnant, bleeding between periods | needs `pregnancy_status: pregnant`, which is never pre-filled |

1. **`pelvic_pain_severity` is never pre-filled, in either direction**, even
   when the app logs a severe intensity. It is how bad the pain is *today*,
   and it is the clause that keeps three of the four rules above in the
   consultation.
2. **`pregnancy_status` is pre-filled as `possibly_pregnant` at most.**
   Pre-filling `pregnant` would let `bleeding_in_pregnancy` fire on two logs.

A test in checklist item 4 re-derives this table from `red_flags.yaml` and
fails if any rule becomes satisfiable from pre-fillable values alone, so a
new red flag cannot silently reopen it. A log can only make the question that
would escalate more likely to be asked.

Everything else the data shows — the counts behind each pre-fill, and
values that failed a rule above — reaches the model as
background through `render_known_background`, framed as ADR 0015 frames the
health note: from her tracking app, unverified, dated by its last entry, and
unable to fire a warning sign on its own.

**Stale data is said to be stale.** Settings and the attach button show when
the data was last updated — *"Cycle data last updated 52 days ago. Upload a
new export to skip these questions again."* — so the window running out is
visible to her, not just to the code.

### 5. Storage

**Daily logs in a tracker vocabulary of our own, not feature values.** A
tracker records days — heavy flow on the 3rd, cramps on the 2nd — while
`features.yaml` describes a pattern, `cycle_length: over_35_days`. Storing a
day as a feature value would make a row mean something its feature does not.
So extraction produces `CycleExtraction`
(`packages/contracts/src/herhealth_contracts/cycle.py`): per day a flow level,
a set of symptoms from a closed list, a pain intensity when the app records
one, and a pregnancy test result. Every field is an enum, a date or an id-shaped
token, so the schema has no place for text from the file — the property
validation of the model's reply relies on. Turning days into feature values is the triage
code's job, where the knowledge base is (checklist item 4).

A `cycle_data` table with one row per user, edited in place exactly as
`health_notes` is: the confirmed `CycleExtraction` as JSON, whether she
confirmed she gets no period pain, and when it was imported. The JSON is
re-validated against the schema whenever it is read, so the column can hold
nothing the vocabulary cannot express. `user_id` cascades on account
deletion. `GET` / `PUT` / `DELETE /accounts/cycle-data`, so it can be
deleted on its own, as the glossary requires. A re-import replaces the
previous one rather than merging, so there is never a question of which
import is current.

**Amended 2026-10-19 by [ADR 0020](0020-she-may-keep-an-uploaded-file-for-30-days.md):**
the file is still discarded by the import, but she may now choose to keep a
copy, in a separate store, for 30 days. Nothing reads a kept file; what
reaches triage is unchanged.

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
- **`cycle_data` is stored in plaintext**, inheriting the same unbuilt
  application-layer encryption ADR 0015 records for `health_notes.content`
  and `messages.content`. It widens what a leaked snapshot contains.
- **The freshness window and cycle minimum are product parameters, not
  sourced figures.** They are configuration, recorded here as chosen values,
  and must not be described as clinically derived.

## Migration checklist

1. This ADR, and the **Cycle data** glossary entry amended to match.
2. Contracts: `CycleExtraction`, the closed tracker vocabulary every
   extractor produces and the model's reply is validated against.
3. No separate field-map file. Each converter maps its app's fields onto the
   tracker vocabulary, and `triage/cycle_data.py` maps the tracker vocabulary
   onto `features.yaml` in one table, with the knowledge base re-checked on
   every call.
4. Triage: the summary (cycle lengths, period durations, per-cycle symptom
   counts), the pre-fill rules of section 4 with the red-flag direction rule
   derived from `red_flags.yaml`, the test that no red flag is satisfiable
   from pre-fillable values alone, and the background wording, each pinned
   by tests. Eval cases carrying cycle data, so `make eval` reports questions
   saved and any action code a pre-fill made worse.
5. Backend: migration `0011`, the model, the routes, the CSV and Apple Health
   converters, model extraction, temp-file handling, deletion tests.
6. Frontend: the attach button, the preview, the Settings section, EN/FR/AR
   strings, RTL.
7. Per-app converters as real sample exports arrive.
