---
status: accepted
---

# What the first real consultations showed

The stopping controller was written against a synthetic three-condition fixture.
`herhealth-triage` ran it against the real knowledge base — 37 features, 12
conditions, 89 evidence rows, 14 red flags — for the first time. Four findings.

Three are recorded rather than fixed, because each is a policy decision that
needs the evaluation set to settle and fixing them quietly would hide the reason
the numbers later moved. The red-flag half of finding 4 **is** fixed: it was a
correctness bug, not a threshold, and the tie-break it needed was already
written down.

Reproduce any of it with `make triage-all`.

## 1. Nothing ever leaves the differential

Every condition starts at 0.0 log-odds, which is plausibility 0.50.
`plausibility_floor` is 0.05, or −2.94 log-odds. Only a `rules_out` row (−4.0)
reaches that in one step, and roughly six `argues_against` rows (−0.5) would be
needed otherwise.

Phase 1 found that 8 of 12 conditions have **zero** eliminating rows, because
sources describe what a condition causes and rarely what argues against it. The
arithmetic consequence is that all 12 conditions are live at the start of every
consultation and all 12 are still live at the end.

That is not a bug in the code; it is what the knowledge base currently supports.
It is written down because three of the four findings below follow from it.

## 2. Question selection barely depends on the answers

`next_question` ranks by separation-per-burden over the *live* conditions. If
every condition is always live, the ranking is very nearly a constant, and the
controller runs a fixed questionnaire.

Observed: all four demonstration cases were asked the same six questions in
almost the same order — `cycle_regularity`, `age_band`, `abnormal_discharge`,
`pelvic_pain_severity`, `period_duration`, `bleeding_heaviness` — regardless of
what was answered.

The visible cost: `itching_and_discharge.yaml` is a case about vulval itching,
and `vulval_itching` was never asked.

`_separation` sums the absolute weight a feature *could* apply without modelling
which answer is likely, so it prefers features with many rows over features that
would discriminate given what has already been said. Making separation
conditional on the current scores is the obvious next step, and it is a change
whose effect on question count has to be measured, not argued.

## 3. Every consultation returns the same action

Three of the four cases — including the one that answers nothing at all — ended
at `URGENT_SAME_DAY`.

The mechanism is sound and deliberate: rule 5 stops with the differential at its
**most urgent** member, which is the single clearest place this design chooses
false alarms over missed escalations. But combined with finding 1,
`pelvic_inflammatory_disease` is in every differential, so `URGENT_SAME_DAY` is
every answer.

A system that says "be seen today" to everyone has perfect red-flag recall and
no information content. Red-flag recall stays gated at 100%; over-triage is
reported but not gated, and this is what that distinction was for. Two levers —
more eliminating rows, and a floor above 0.50 so untouched conditions fall out —
and both change the safety profile, so both wait for the evaluation set.

## 4. Rule 4 can under-triage, and rule 1 could under-escalate

Two inconsistencies in the ordering, both found by tests. The second is fixed;
the first is not, because it is a policy question rather than a bug in isolation.

**Rule 4 returns the top condition's action, not the most urgent live one.**
Rules 3 and 5 both take `most_urgent` over the differential; rule 4 takes
`ranked()[0]`. So a confident `ROUTINE_APPOINTMENT` can be returned while an
`URGENT_SAME_DAY` condition sits unexcluded above the floor. This is
under-triage manufactured by the controller. It does not currently fire against
the real knowledge base — rule 4 never triggered in any demonstration case — but
it is latent, and raising `stop_confidence` or adding evidence will wake it.

Pinned by `test_an_unresolved_differential_never_concludes_below_its_worst_member`,
marked `xfail(strict=True)` so it fails loudly when fixed.

**Rule 1 fired on the first matching rule, not the most severe one. FIXED.**
`sudden_severe_pain.yaml` describes sudden onset of severe pelvic pain, which
matches `sudden_severe_pelvic_pain` (EMERGENCY). It came back `URGENT_SAME_DAY`,
because the controller asked `pelvic_pain_severity`, matched the single-clause
`severe_pelvic_pain` rule on that answer alone, and stopped — never asking
`pain_onset`, the one question that would have escalated further. A red flag was
pre-empting a *more severe* red flag that was one question away.

Unlike the other three, this needed no measurement to settle: it is a
correctness bug, and the tie-break was already written down — *whenever a design
choice trades false alarms against missed escalations, choose false alarms.*

Both halves are fixed. See "Escalation probing" below.

## Escalation probing — how finding 4's red-flag half was fixed

Two changes in `engine.py`:

**Matching takes the most severe rule, not the first in file order.** When
several rules match the same answers, the escalation must not depend on how the
YAML happened to be arranged.

**A fired rule does not conclude while a more severe one is one answer away.**
Before returning `RED_FLAG`, the controller asks about any rule that is strictly
more severe and has **exactly one** outstanding clause on a feature not yet put
to the user, provided at least one of its other clauses already matches.

Each condition earns its place:

| Condition | Why |
|---|---|
| Exactly one outstanding clause | Keeps the bound structural — every probe either fires the rule or kills it, so the screen terminates. Chasing rules two answers out would not |
| Feature not yet asked | A feature already answered, *including answered `unknown`*, can never satisfy the clause. Continuing would ask a question whose answer is already in |
| At least one clause already matching | Scopes probing to escalations of the presentation in hand. Without it, any unrelated single-clause emergency rule would be pulled in the moment anything fired |

Probes are ranked by how many more severe rules the answer would settle, then by
burden, then by id. Preferring coverage is what keeps the screen short: one
question can close several rules at once.

**There is no probe budget, and that is deliberate.** The bound comes from the
knowledge base rather than from a number someone has to guess right. A budget
low enough to protect patience would silently drop the last few emergency rules,
which is the failure this change exists to remove.

**The cost is real and is pinned by a test.** Once severe pelvic pain is known,
six EMERGENCY rules are each one answer from firing, so
`sudden_severe_pain.yaml` now takes ten questions rather than four — six of them
the escalation screen. That runs past `max_questions`, on purpose: the question
budget is a judgement about patience, and emergency screening is not subject to
it. Every one of the six is a burden-1 or burden-2 yes/no question that is a
single answer away from an emergency.

It is still worth watching. The screen interacts with finding 2: three of the
first four questions in that case were spent on features the ranking preferred
for no good reason, and better question selection would shorten the whole
consultation rather than just the screen. Average questions asked is a reported
metric, and this is what it is for.

## Consequences

- These four are the phase 2 findings, and they are the input to threshold
  tuning. `weights.yaml` already says its numbers are uncalibrated; this says
  what specifically is wrong with them.
- The demonstration cases in `services/backend/cases/` are pinned by tests, so
  any change to weights or ranking shows up as a named failing case rather than
  as a silent shift.
- None of this is reported as a result. It is behaviour of an untuned controller
  over a source-traceable but not clinician-adjudicated knowledge base, and it
  is stated that way wherever it appears.
