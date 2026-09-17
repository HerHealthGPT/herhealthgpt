# Observed triage behaviour

Worked examples captured from live consultations through the deployed system.
Written to be lifted into the project report.

---

## What this document is, and is not

These are **transcripts of real consultations**, reproduced verbatim from the
`messages` table, not constructed illustrations. Each shows what the system
asked, what it was told, and what it concluded.

**Standing limitation, which applies to every result below.** The knowledge
base is **source-traceable but not clinician-adjudicated**, and the benchmark
labels this project reports elsewhere are **silver**, not clinician-adjudicated.
Nothing here should be described as clinically validated, expert-reviewed or
verified. Coverage gaps are a stated limitation of the knowledge base, not an
oversight, and are reported alongside coverage wherever coverage is reported.

**The system reports urgency and gives informational guidance. It does not
diagnose.** Where a conclusion names conditions it does so as *"may match
patterns our sources associate with…"* — never as an assertion about what the
user has.

### Method

Consultations were conducted through the deployed stack — Next.js frontend,
FastAPI backend, retrieval service over the sentence-level passage index, and
the configured reasoning service. Transcripts and the full `TriageDecision` for
every assistant turn are persisted per turn and were read back from the
database rather than transcribed from the screen.

The deployment ran in its `vllm` triage mode, which routes a turn to the
self-hosted adapter and falls back to the hosted base model when that does not
return a schema-valid decision. Which component produced any individual turn is
recorded per message in `messages.served_by`, together with the reason for any
failed attempt; that record is the authority for per-turn attribution. It is
not reproduced in the examples below, which document end-to-end system
behaviour rather than component provenance.

---

## 1. A multi-turn consultation concluding at routine urgency

Four clarifying questions, then a conclusion. The opening message is vague; the
system narrows before concluding rather than answering the first thing it hears.

> **User** — My periods have been irregular lately
>
> **System** — Have you noticed any unusual vaginal discharge?
>
> **User** — no
>
> **System** — Have you noticed dark, velvety patches of skin, especially on
> your neck, armpits or groin?
>
> **User** — yes on my neck
>
> **System** — Have you noticed more hair growth than usual on your face, chest
> or back?
>
> **User** — yes on my face
>
> **System** — Has the hair on your head been thinning?
>
> **User** — yes thinning hair
>
> **System** — The combination of irregular periods, dark velvety skin patches,
> extra hair growth, and thinning scalp hair can all be linked to hormonal
> changes that a healthcare provider can assess.

**Outcome:** `ROUTINE_APPOINTMENT`, four questions asked.

**What this demonstrates.**

- **Clarification before conclusion.** The system did not answer the opening
  message. It asked four questions and concluded only once the picture was
  specific.
- **A coherent line of questioning.** `acanthosis_nigricans`,
  `excess_hair_growth` and `scalp_hair_thinning` are the features the evidence
  grid associates with one condition, asked in sequence.
- **Grounding.** The conclusion cites an authored evidence row whose own
  `source_quote` is the sentence the row was derived from: *"Signs that you
  have high levels of androgens: Extra hair growth on your face, chin, and body
  (hirsutism) Acne Thinning of scalp hair"* — attributed to the Office on
  Women's Health.
- **No diagnosis.** The conclusion describes the pattern and routes to a
  clinician. It names no condition to the user and asserts nothing about what
  she has.

**A defect visible in the same run.** The first question asked about
`abnormal_discharge`. In the evidence grid that feature touches only one of the
conditions raised by irregular periods, and none of the three most strongly
supported ones — so neither answer could move the top of the differential. The
questions that followed were well chosen; the first was not. The schema
guarantees a question comes from the closed feature vocabulary, but nothing
checks that the chosen question is the discriminating one.

---

## 2. Escalation on a warning sign, after one question

> **User** — i have a really bad pain in my lower tummy
>
> **System** — Have you been unusually tired, breathless, or dizzy?
>
> **User** — yes i feel faint and dizzy
>
> **System** — Severe pelvic pain combined with faintness requires emergency
> care now.

**Outcome:** `EMERGENCY`, rule `pelvic_pain_with_faintness`, one question asked.

**What this demonstrates.**

- **Escalation interrupts the consultation.** The question budget is irrelevant
  once a warning sign matches; the system concluded on the second turn.
- **Urgency-first phrasing.** The user-facing text leads with what to do rather
  than opening with caveats.
- **Conditions named only at `EMERGENCY`.** The decision carried five
  `matching_conditions` alongside the `red_flag_id`. This is the narrow
  allowance for emergency conclusions — at every lower urgency a red-flag
  conclusion names nothing and escalates on the symptom pattern alone.

---

## 3. Escalation reached through a longer consultation

Six questions, then a warning sign matched on the sixth answer.

> **User** — My periods have been irregular lately
>
> **System** — Are your periods usually regular, irregular, or have they
> stopped recently?
>
> **User** — they stopped recently
>
> **System** — Have you been extremely or unusually tired?
>
> **User** — i feel extremely tired
>
> **System** — Do you get any bleeding between your periods?
>
> **User** — No
>
> **System** — How bad does the pain get — mild, moderate, or severe enough to
> stop you doing normal activities?
>
> **User** — i have extereme pain when i get my period
>
> **System** — Roughly how many days are there between the start of one period
> and the next?
>
> **User** — around 50 to 60 days
>
> **System** — Have you felt faint, or actually passed out?
>
> **User** — yes i feel faint and dizzy
>
> **System** — Severe pelvic pain combined with feeling faint is a medical
> emergency. You need to go to your local emergency department or call
> emergency services now. Other urgent conditions can't be ruled out by message
> alone.

**Outcome:** `EMERGENCY`, rule `pelvic_pain_with_faintness`, six questions asked.

**What this demonstrates.**

- **A consultation that began at routine urgency ended at emergency.** Nothing
  in the opening message suggested escalation. The system did not settle on the
  urgency implied by the first thing it was told.
- **Misspelled and colloquial input was understood.** *"i have extereme pain
  when i get my period"* was mapped onto the severity vocabulary; *"around 50
  to 60 days"* onto the cycle-length vocabulary.
- **The conclusion states its own limits** — that other urgent conditions
  cannot be ruled out by message alone.

---

## 4. Escalation on a two-symptom pattern, with no question asked

> **User** — I have pelvic pain and a sharp pain at the tip of my shoulder, it
> started today.
>
> **System** — *(concluded immediately, without asking anything)*

**Outcome:** `EMERGENCY`, rule `pelvic_pain_with_shoulder_tip_pain`, no
questions asked.

**What this demonstrates.** The opening message answered every clause of a
warning-sign rule at once. The system asked nothing further and escalated on
the first turn — the correct behaviour when the pattern is already complete.

**A defect in the user-facing text of this run.** The message shown to the user
quoted the internal rule identifier (`pelvic_pain_with_shoulder_tip_pain`),
used the phrase "red-flag warning sign", and appended a safety disclaimer that
the interface already displays beneath every answer. The prompt forbids all
three. The triage outcome was correct; the wording leaked internal vocabulary a
user should never see.

---

## Summary of observed behaviour

**Consistent across runs.**

| Behaviour | Evidence |
|---|---|
| Asks before concluding on a vague opening message | §1 (4 questions), §3 (6 questions) |
| Escalates immediately when a warning sign completes | §2 (1 question), §4 (0 questions) |
| Records answers against a closed feature vocabulary | colloquial and misspelled input mapped correctly, §3 |
| Grounds conclusions in cited sources | §1 cites an authored evidence row with its source quote |
| Never asserts a diagnosis | every conclusion routes to care without telling the user what she has |
| Names conditions only at `EMERGENCY` | §2 and §4 carry `matching_conditions`; lower-urgency red-flag conclusions do not |

**Defects observed, reported rather than omitted.**

| Defect | Where | Nature |
|---|---|---|
| First question chosen had no discriminating value | §1 | Schema-valid, judgement-poor: the closed vocabulary constrains which questions *exist*, not which is *useful* |
| Internal identifiers and disclaimer text leaked into user-facing wording | §4 | Prompt-level rule violated; no code-level check enforces it |

Both defects share a cause worth stating plainly in the report: the schema
guarantees a decision is *representable* — a real feature id, a real action
code, a real rule id — and deliberately does not guarantee it is *well judged*.
That gap is a known and documented property of the current architecture, not an
unanticipated failure.
