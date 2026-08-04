---
status: accepted
---

# What the first real consultations showed

The stopping controller was written against a synthetic three-condition fixture.
`herhealth-triage` ran it against the real knowledge base — 37 features, 12
conditions, 89 evidence rows, 14 red flags — for the first time. Four findings,
recorded here rather than fixed, because each is a policy decision that needs
the evaluation set to settle and because fixing them quietly would hide the
reason the numbers later moved.

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

## 4. Rule 4 can under-triage, and rule 1 can under-escalate

Two inconsistencies in the ordering, both found by tests.

**Rule 4 returns the top condition's action, not the most urgent live one.**
Rules 3 and 5 both take `most_urgent` over the differential; rule 4 takes
`ranked()[0]`. So a confident `ROUTINE_APPOINTMENT` can be returned while an
`URGENT_SAME_DAY` condition sits unexcluded above the floor. This is
under-triage manufactured by the controller. It does not currently fire against
the real knowledge base — rule 4 never triggered in any demonstration case — but
it is latent, and raising `stop_confidence` or adding evidence will wake it.

Pinned by `test_an_unresolved_differential_never_concludes_below_its_worst_member`,
marked `xfail(strict=True)` so it fails loudly when fixed.

**Rule 1 fires on the first matching rule, not the most severe one.**
`sudden_severe_pain.yaml` describes sudden onset of severe pelvic pain, which
matches `sudden_severe_pelvic_pain` (EMERGENCY). It came back `URGENT_SAME_DAY`,
because the controller asked `pelvic_pain_severity`, matched the single-clause
`severe_pelvic_pain` rule on that answer alone, and stopped — never asking
`pain_onset`, the one question that would have escalated further.

So a red flag can pre-empt a *more severe* red flag that was one question away.
Two candidate fixes, neither free:

- Before concluding on a rule, ask any unasked clause belonging to a strictly
  more severe rule that shares an already-matched feature. Costs a question,
  only on cases that are already escalating.
- Match rules by severity rather than file order. Cheaper, but only helps when
  both rules already match, which is not this case.

The first is the conservative one and is therefore the likely choice. It is not
made here because it changes the question budget on the exact cases where
latency matters most.

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
