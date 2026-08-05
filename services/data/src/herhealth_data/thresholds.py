"""Derive and check the tunable numbers in ``weights.yaml``.

"We chose them" is not a defensible answer for a threshold that decides whether
someone is told to see a doctor. This module supplies the answer that is
available to us without calibration data: **the numbers are consequences of
stated requirements, and the requirements are arguable.**

Same epistemics as the rest of the knowledge base. A clinical row is defensible
because it traces to a source sentence; a threshold is defensible because it
traces to a written requirement about how many findings should be needed to
reach a conclusion. Neither claims to be measured.

The scale has one free parameter
--------------------------------
Log-odds can be multiplied by any positive constant without changing a single
decision, because every threshold rescales with it. So ``strong_support = 1.5``
is not a claim about anything — it is a choice of unit, like choosing metres
over feet.

What survives rescaling, and therefore what actually encodes the design:

* the **ratios** between the weights, and
* **where each threshold sits relative to reachable row combinations**.

Those are what this module reports.

The counting argument
---------------------
A threshold is only meaningful relative to what the evidence can actually
produce. With weights of +1.5 and +0.6, a condition's score can only ever land
on sums of those — 0.6, 1.2, 1.5, 1.8, 2.1 and so on. A threshold sitting in a
gap between two reachable sums has a clear meaning ("more than one weak row").
A threshold sitting *just* above a reachable sum has the same meaning by luck,
and a small edit elsewhere silently flips it.

So the check this module performs is: **for each threshold, how much room is
there on either side?** A threshold with a 0.019 log-odds margin is fragile
however sensible its value looks.

Run it with ``make thresholds``.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product

from herhealth_contracts.knowledge import EvidenceStrength, Weights
from herhealth_contracts.scoring import log_odds_for, plausibility

__all__ = [
    "FRAGILE_MARGIN",
    "Combination",
    "ThresholdPlacement",
    "analyse",
    "reachable_scores",
    "robust_midpoint",
]

#: A threshold closer than this (in log-odds) to a reachable score is fragile:
#: its meaning depends on an accident rather than on a decision. 0.1 is itself a
#: judgement, but a transparent one — it is roughly a sixth of a weak_support
#: row, so anything under it cannot be an intended separation.
FRAGILE_MARGIN = 0.1

#: How many supporting rows a single condition realistically accumulates. Three
#: covers every combination that matters; the densest condition in the knowledge
#: base has 12 rows total but they are spread across mutually exclusive answers.
MAX_ROWS = 3


@dataclass(frozen=True, slots=True)
class Combination:
    """A reachable score, and the rows that would produce it."""

    score: float
    strong: int
    weak: int

    @property
    def rows(self) -> int:
        return self.strong + self.weak

    def describe(self) -> str:
        parts = []
        if self.strong:
            parts.append(f"{self.strong}×strong")
        if self.weak:
            parts.append(f"{self.weak}×weak")
        return " + ".join(parts) or "nothing"


def reachable_scores(weights: Weights, max_rows: int = MAX_ROWS) -> list[Combination]:
    """Every score a condition can actually reach from supporting rows.

    Supporting rows only. Eliminating rows are handled separately because they
    move in the opposite direction and the floor is the threshold that matters
    for them.
    """
    strong = weights.log_odds[EvidenceStrength.STRONG_SUPPORT]
    weak = weights.log_odds[EvidenceStrength.WEAK_SUPPORT]

    seen: dict[float, Combination] = {}
    for n_strong, n_weak in product(range(max_rows + 1), repeat=2):
        if not 1 <= n_strong + n_weak <= max_rows:
            continue
        score = round(n_strong * strong + n_weak * weak, 6)
        # Keep the cheapest explanation of a score a user could reach.
        if score not in seen or (n_strong + n_weak) < seen[score].rows:
            seen[score] = Combination(score=score, strong=n_strong, weak=n_weak)
    return sorted(seen.values(), key=lambda c: c.score)


@dataclass(frozen=True, slots=True)
class ThresholdPlacement:
    """Where one threshold sits among the scores evidence can produce."""

    name: str
    value: float
    log_odds: float
    below: Combination | None
    above: Combination | None

    @property
    def margin_below(self) -> float | None:
        return None if self.below is None else self.log_odds - self.below.score

    @property
    def margin_above(self) -> float | None:
        return None if self.above is None else self.above.score - self.log_odds

    @property
    def tightest_margin(self) -> float | None:
        margins = [m for m in (self.margin_below, self.margin_above) if m is not None]
        return min(margins) if margins else None

    @property
    def is_fragile(self) -> bool:
        tightest = self.tightest_margin
        return tightest is not None and tightest < FRAGILE_MARGIN

    @property
    def meaning(self) -> str:
        """What crossing this threshold requires, in rows."""
        if self.below is None:
            return f"anything below {self.above.describe()}" if self.above else "unreachable"
        return f"more than {self.below.describe()}"

    def robust_value(self) -> float | None:
        """Where the threshold would sit with equal room on both sides."""
        if self.below is None or self.above is None:
            return None
        return plausibility(robust_midpoint(self.below.score, self.above.score))


def robust_midpoint(lower: float, upper: float) -> float:
    """Halfway between two reachable scores, in log-odds.

    In log-odds rather than in plausibility: the plausibility scale is
    compressed at the ends, so a midpoint taken there would sit closer to one
    neighbour than the other and defeat the purpose.
    """
    return (lower + upper) / 2


def analyse(weights: Weights) -> list[ThresholdPlacement]:
    """Place every threshold among the reachable scores."""
    combos = reachable_scores(weights)
    named = [
        ("plausibility_floor", weights.plausibility_floor),
        ("stop_confidence", weights.stop_confidence),
        ("self_care_stop_confidence", weights.self_care_stop_confidence),
    ]

    placements: list[ThresholdPlacement] = []
    for name, value in named:
        target = log_odds_for(value)
        below = max((c for c in combos if c.score < target), key=lambda c: c.score, default=None)
        above = min((c for c in combos if c.score >= target), key=lambda c: c.score, default=None)
        placements.append(
            ThresholdPlacement(
                name=name, value=value, log_odds=target, below=below, above=above
            )
        )
    return placements


def eliminating_rows_needed(weights: Weights) -> float:
    """How many ``argues_against`` rows it takes to reach the floor from zero."""
    against = weights.log_odds[EvidenceStrength.ARGUES_AGAINST]
    return abs(log_odds_for(weights.plausibility_floor) / against)


def rules_out_ceiling(weights: Weights) -> float:
    """Most prior support a ``rules_out`` row can still overcome, in log-odds.

    See docs/adr/0009. Weights add, so ``rules_out`` is not unconditional; this
    is the number that says how conditional it is.
    """
    return log_odds_for(weights.plausibility_floor) - weights.log_odds[EvidenceStrength.RULES_OUT]
