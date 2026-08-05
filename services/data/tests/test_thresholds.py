"""Tests for the threshold derivation.

The point of this module is that a threshold should mean something *by
decision*, not by accident. These tests check the machinery that detects the
difference.
"""

from __future__ import annotations

from math import exp, log

import pytest
from herhealth_contracts.knowledge import EvidenceStrength, Weights

from herhealth_data.thresholds import (
    FRAGILE_MARGIN,
    analyse,
    eliminating_rows_needed,
    reachable_scores,
    robust_midpoint,
    rules_out_ceiling,
)

BASE: dict[str, object] = {
    "log_odds": {
        "strong_support": 1.5,
        "weak_support": 0.6,
        "neutral": 0.0,
        "argues_against": -0.5,
        "rules_out": -4.0,
    },
    "plausibility_floor": 0.05,
    "stop_confidence": 0.65,
    "self_care_stop_confidence": 0.85,
    "stop_margin": 0.15,
    "max_questions": 6,
}


def weights(**overrides: object) -> Weights:
    return Weights.model_validate({**BASE, **overrides})


# --------------------------------------------------------------------------
# The claim the documentation makes about the weights
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("strength", "multiplier"),
    [
        (EvidenceStrength.STRONG_SUPPORT, 4.5),
        (EvidenceStrength.WEAK_SUPPORT, 1.8),
        (EvidenceStrength.NEUTRAL, 1.0),
        (EvidenceStrength.ARGUES_AGAINST, 0.61),
    ],
)
def test_each_weight_reads_as_an_odds_multiplier(
    strength: EvidenceStrength, multiplier: float
) -> None:
    """Adding log-odds multiplies odds, which is why the weights are explainable
    at all: +1.5 means "about 4.5x more likely". weights.yaml and the docs both
    state these multipliers, so pin them."""
    assert exp(weights().log_odds[strength]) == pytest.approx(multiplier, abs=0.05)


def test_neutral_multiplies_by_exactly_one() -> None:
    """Which is precisely why a neutral row is an omitted row."""
    assert exp(weights().log_odds[EvidenceStrength.NEUTRAL]) == 1.0


def test_support_is_moderate_never_conclusive() -> None:
    """No level reaches the conventional "large, often conclusive" band (~10x).
    One sentence from a public health page is not conclusive evidence."""
    strongest = exp(weights().log_odds[EvidenceStrength.STRONG_SUPPORT])
    assert strongest < 10.0


def test_belief_accumulates_faster_than_it_is_lost() -> None:
    """The asymmetry that protects against under-triage: wrongly dropping a
    condition costs more than asking one more question."""
    w = weights()
    assert abs(w.log_odds[EvidenceStrength.ARGUES_AGAINST]) < w.log_odds[
        EvidenceStrength.WEAK_SUPPORT
    ]


# --------------------------------------------------------------------------
# Reachable scores
# --------------------------------------------------------------------------


def test_only_sums_of_the_weights_are_reachable() -> None:
    scores = [c.score for c in reachable_scores(weights())]
    assert 0.6 in scores and 1.2 in scores and 1.5 in scores
    assert 1.0 not in scores  # no combination of 1.5 and 0.6 makes 1.0


def test_scores_come_back_in_order() -> None:
    scores = [c.score for c in reachable_scores(weights())]
    assert scores == sorted(scores)


def test_two_weak_rows_score_less_than_one_strong() -> None:
    """A consequence worth knowing: NO threshold can admit two weak rows while
    excluding one strong row. Any requirement phrased as "at least two findings"
    is unsatisfiable on this scale."""
    w = weights()
    assert 2 * w.log_odds[EvidenceStrength.WEAK_SUPPORT] < w.log_odds[
        EvidenceStrength.STRONG_SUPPORT
    ]


# --------------------------------------------------------------------------
# Fragility — the actual point
# --------------------------------------------------------------------------


def test_the_shipped_stop_confidence_is_fragile() -> None:
    """REGRESSION-ish. 0.65 clears "one weak row" by 0.019 log-odds. It enforces
    the right requirement by accident, and a small edit to weak_support would
    silently let one passing mention conclude a consultation."""
    placement = next(p for p in analyse(weights()) if p.name == "stop_confidence")
    assert placement.is_fragile
    assert placement.margin_below is not None
    assert placement.margin_below < 0.05


def test_a_threshold_in_a_gap_is_not_fragile() -> None:
    """0.711 sits midway between one weak row and two."""
    placement = next(
        p for p in analyse(weights(stop_confidence=0.711)) if p.name == "stop_confidence"
    )
    assert not placement.is_fragile


def test_the_robust_alternative_is_actually_robust() -> None:
    placement = next(p for p in analyse(weights()) if p.name == "stop_confidence")
    robust = placement.robust_value()
    assert robust is not None
    replaced = next(
        p for p in analyse(weights(stop_confidence=round(robust, 3))) if p.name == "stop_confidence"
    )
    assert not replaced.is_fragile
    assert replaced.tightest_margin is not None
    assert replaced.tightest_margin > FRAGILE_MARGIN


def test_a_threshold_still_means_the_same_thing_after_being_made_robust() -> None:
    """Robustness must not change the requirement, only the margin."""
    before = next(p for p in analyse(weights()) if p.name == "stop_confidence")
    after = next(
        p for p in analyse(weights(stop_confidence=0.711)) if p.name == "stop_confidence"
    )
    assert before.meaning == after.meaning == "more than 1×weak"


def test_the_midpoint_is_taken_in_log_odds() -> None:
    """Not in plausibility. That scale is compressed at the ends, so a midpoint
    taken there would sit closer to one neighbour and defeat the purpose."""
    assert robust_midpoint(0.6, 1.2) == pytest.approx(0.9)


# --------------------------------------------------------------------------
# Elimination
# --------------------------------------------------------------------------


def test_six_argues_against_rows_are_needed_to_eliminate() -> None:
    assert eliminating_rows_needed(weights()) == pytest.approx(5.9, abs=0.1)


def test_rules_out_is_not_unconditional() -> None:
    """See ADR 0009. It only overcomes prior support below ~+1.06 log-odds, and
    a single strong_support row (+1.5) already exceeds that."""
    ceiling = rules_out_ceiling(weights())
    assert ceiling == pytest.approx(1.06, abs=0.01)
    assert weights().log_odds[EvidenceStrength.STRONG_SUPPORT] > ceiling


# --------------------------------------------------------------------------
# Scale invariance — why the unit is not a claim
# --------------------------------------------------------------------------


def test_rescaling_every_weight_changes_no_meaning() -> None:
    """Log-odds can be multiplied by any positive constant without changing a
    decision, provided the thresholds move with them. So `strong_support = 1.5`
    is a choice of unit, like metres, not a claim about anything."""
    k = 2.0
    scaled = weights(
        log_odds={s.value: v * k for s, v in weights().log_odds.items()},
        plausibility_floor=1 / (1 + exp(-k * log(0.05 / 0.95))),
        stop_confidence=1 / (1 + exp(-k * log(0.65 / 0.35))),
        self_care_stop_confidence=1 / (1 + exp(-k * log(0.85 / 0.15))),
    )
    assert [p.meaning for p in analyse(scaled)] == [p.meaning for p in analyse(weights())]
