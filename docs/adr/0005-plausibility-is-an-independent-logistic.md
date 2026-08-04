---
status: accepted
---

# Plausibility is an independent logistic, not a softmax

Evidence accumulates as log-odds per condition; the stopping thresholds are
authored on 0–1. We convert with an independent logistic — each condition's
plausibility depends only on its own score — rather than a softmax across the
differential.

## Why not softmax

**A softmax cannot express "none of these fit."** It normalises to 1 whatever it
is given, so a user describing a condition outside the modelled fourteen would
still see the least-bad candidate emerge with high plausibility: confidence
manufactured from nothing.

For this system that is the worst available failure shape, because
`normal_variation` carries a `SELF_CARE` baseline. A user with an unmodelled
condition and uniformly weak evidence could see `normal_variation` float to the
top purely because everything else scored worse, and be told to stay home —
under-triage produced by the arithmetic itself rather than by a bad row.

Two further reasons:

- **Thresholds keep their meaning as the differential grows.** Under softmax the
  uniform score falls from 0.25 at four conditions to 0.07 at fourteen, so every
  threshold would need re-tuning each time a condition is added.
- **`rules_out` does what `weights.yaml` claims.** That file states a single
  `rules_out` row drops a condition below `plausibility_floor` *regardless of
  accumulated support*. Under a logistic that is true and now enforced by a model
  validator: the floor sits at −2.94 log-odds and `rules_out` is −4.0. Under a
  softmax the sentence would be false, since the outcome would depend on what
  every other condition scored.

## Consequences

`stop_margin` is less natural here. Two conditions may both sit at 0.9 with no
margin between them, so the margin rule fires less often and the controller
leans harder on `max_questions`. That is arguably correct — both are plausible,
so keep asking — but it is a real difference from a normalised distribution and
should be watched in evaluation.

Converting the thresholds into log-odds also exposed that they are low relative
to the weights: a single `strong_support` row reaches 0.818 and clears
`stop_confidence` of 0.65 on its own. That is recorded in `weights.yaml` as the
first tuning experiment rather than adjusted by argument here.

The conversion lives in `packages/contracts/src/herhealth_contracts/scoring.py`
because both the Phase 2 controller and the Phase 3 evaluation harness need it,
and the import rule puts shared definitions in contracts.
