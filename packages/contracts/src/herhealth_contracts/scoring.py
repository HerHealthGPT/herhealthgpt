"""How accumulated evidence becomes plausibility.

Evidence rows carry ordinal strengths which ``weights.yaml`` maps to log-odds.
Those accumulate additively per condition, so a condition's running score is
unbounded and may be negative. The stopping thresholds, however, are expressed
on 0-1. This module is the conversion, and it is the single definition of it.

Independent logistic, not softmax
---------------------------------
Each condition's plausibility is computed from its own score alone::

    plausibility = 1 / (1 + exp(-log_odds))

Conditions do not compete for a fixed total. Several may be plausible at once,
and — critically — *all* of them may be implausible.

That last property is the reason for the choice. A softmax normalises to 1
whatever it is given, so when a user describes something outside the modelled
conditions, the least-bad condition still emerges with high plausibility:
confidence manufactured out of nothing. For this system that is the worst
available failure shape, because ``normal_variation`` carries a ``SELF_CARE``
baseline. A user with an unmodelled condition and uniformly weak evidence could
see ``normal_variation`` float to the top purely because everything else scored
worse, and be told to stay home. Under-triage produced by the arithmetic itself.

A logistic can say "everything is low". A softmax structurally cannot.

Two further consequences, both wanted:

* **Thresholds keep their meaning as conditions are added.** Under softmax the
  uniform score falls from 0.25 at four conditions to 0.07 at fourteen, so every
  threshold would need re-tuning each time the differential grows.
* **``rules_out`` does what ``weights.yaml`` claims.** That file states a single
  ``rules_out`` row drops a condition below ``plausibility_floor`` *regardless of
  accumulated support*. Here that is true and checkable: the floor of 0.05 sits
  at log-odds -2.94, and ``rules_out`` is -4.0. Under a softmax the same
  sentence would be false, because whether a condition fell below the floor
  would depend on what every other condition scored.

The cost, recorded honestly: ``stop_margin`` is less natural here. Two
conditions may both sit at 0.9 with no margin between them, so the margin rule
fires less often and the controller leans harder on ``max_questions``. That is
arguably the right behaviour — both are plausible, so keep asking — but it is a
real difference from a normalised distribution.

See docs/adr/0005-plausibility-is-an-independent-logistic.md.
"""

from __future__ import annotations

import math
from typing import Final

__all__ = [
    "MAX_LOG_ODDS",
    "log_odds_for",
    "plausibility",
]

#: Clamp for the logistic input. Beyond this the result is 1.0 or 0.0 to float
#: precision anyway, and clamping keeps ``exp`` from overflowing on a condition
#: that has accumulated a great many supporting rows.
MAX_LOG_ODDS: Final[float] = 60.0


def plausibility(log_odds: float) -> float:
    """Convert an accumulated log-odds score to plausibility in [0, 1].

    Independent per condition — see the module docstring for why this is not a
    softmax. A score of 0.0, meaning no evidence either way, gives 0.5.
    """
    clamped = max(-MAX_LOG_ODDS, min(MAX_LOG_ODDS, log_odds))
    return 1.0 / (1.0 + math.exp(-clamped))


def log_odds_for(target: float) -> float:
    """The score at which a condition reaches ``target`` plausibility.

    The inverse of :func:`plausibility`. Used to express the 0-1 thresholds in
    ``weights.yaml`` in the units the controller actually accumulates, which is
    what makes a threshold checkable against the evidence weights.

    Raises for 0 and 1, which are unreachable rather than merely extreme.
    """
    if not 0.0 < target < 1.0:
        raise ValueError(f"plausibility must be strictly between 0 and 1, got {target}")
    return math.log(target / (1.0 - target))
