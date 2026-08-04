"""Tests for the log-odds to plausibility conversion.

The properties that matter are the ones the choice of a logistic over a softmax
was made for, so those are what get asserted.
"""

from __future__ import annotations

import math

import pytest

from herhealth_contracts.knowledge import EvidenceStrength, Weights
from herhealth_contracts.scoring import MAX_LOG_ODDS, log_odds_for, plausibility


def weights(**overrides: object) -> Weights:
    values: dict[str, object] = {
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
    }
    values.update(overrides)
    return Weights(**values)  # type: ignore[arg-type]


# --------------------------------------------------------------------------
# The conversion
# --------------------------------------------------------------------------


def test_no_evidence_is_one_half() -> None:
    assert plausibility(0.0) == pytest.approx(0.5)


def test_it_is_monotonic() -> None:
    scores = [-5.0, -1.0, 0.0, 1.0, 5.0]
    values = [plausibility(s) for s in scores]
    assert values == sorted(values)


def test_it_stays_in_range_at_extremes() -> None:
    assert 0.0 <= plausibility(-1e6) < 0.001
    assert 0.999 < plausibility(1e6) <= 1.0


def test_it_does_not_overflow_on_a_large_score() -> None:
    """A condition with many supporting rows must not crash the controller."""
    assert plausibility(10_000.0) == pytest.approx(1.0)
    assert plausibility(-10_000.0) == pytest.approx(0.0)


def test_round_trips() -> None:
    for target in (0.05, 0.25, 0.5, 0.65, 0.85, 0.99):
        assert plausibility(log_odds_for(target)) == pytest.approx(target)


@pytest.mark.parametrize("bad", [0.0, 1.0, -0.1, 1.1])
def test_unreachable_targets_are_rejected(bad: float) -> None:
    with pytest.raises(ValueError, match="strictly between"):
        log_odds_for(bad)


def test_clamp_is_wide_enough_to_be_irrelevant_in_practice() -> None:
    """The clamp exists to stop exp overflowing, not to shape behaviour."""
    assert plausibility(MAX_LOG_ODDS) == pytest.approx(1.0)
    assert math.isclose(plausibility(MAX_LOG_ODDS), plausibility(MAX_LOG_ODDS * 2))


# --------------------------------------------------------------------------
# Why a logistic and not a softmax
# --------------------------------------------------------------------------


def test_conditions_do_not_compete() -> None:
    """Two well-supported conditions may both be plausible."""
    assert plausibility(3.0) > 0.9
    assert plausibility(3.0) + plausibility(3.0) > 1.0, "scores must not be a distribution"


def test_everything_can_be_implausible_at_once() -> None:
    """The property a softmax cannot express, and the reason for the choice.

    A user describing something outside the modelled conditions must not see the
    least-bad condition promoted to high plausibility.
    """
    weak_scores = [-1.0, -1.5, -2.0, -0.8]
    assert all(plausibility(s) < 0.5 for s in weak_scores)
    assert max(plausibility(s) for s in weak_scores) < 0.5


# --------------------------------------------------------------------------
# The claim weights.yaml makes for rules_out
# --------------------------------------------------------------------------


def test_rules_out_alone_falls_below_the_floor() -> None:
    w = weights()
    ruled_out = w.log_odds[EvidenceStrength.RULES_OUT]
    assert plausibility(ruled_out) < w.plausibility_floor


def test_rules_out_beats_accumulated_support() -> None:
    """"Regardless of accumulated support" — check it, do not trust the comment."""
    w = weights()
    strong = w.log_odds[EvidenceStrength.STRONG_SUPPORT]
    ruled_out = w.log_odds[EvidenceStrength.RULES_OUT]
    assert plausibility(2 * strong + ruled_out) < 0.5


def test_a_rules_out_that_cannot_rule_out_is_rejected() -> None:
    """The schema enforces the claim rather than leaving it to a comment."""
    toothless = weights().log_odds | {EvidenceStrength.RULES_OUT: -1.0}
    with pytest.raises(ValueError, match="would not rule anything out"):
        weights(log_odds={k.value: v for k, v in toothless.items()})


# --------------------------------------------------------------------------
# Thresholds expressed in the units the controller accumulates
# --------------------------------------------------------------------------


def test_thresholds_convert_to_log_odds() -> None:
    w = weights()
    assert w.plausibility_floor_log_odds == pytest.approx(-2.944, abs=0.01)
    assert w.stop_confidence_log_odds == pytest.approx(0.619, abs=0.01)
    assert w.self_care_stop_confidence_log_odds == pytest.approx(1.734, abs=0.01)


def test_the_self_care_bar_stays_higher_in_either_unit() -> None:
    w = weights()
    assert w.self_care_stop_confidence > w.stop_confidence
    assert w.self_care_stop_confidence_log_odds > w.stop_confidence_log_odds


def test_one_strong_row_currently_clears_the_routine_bar() -> None:
    """Documents the known tuning problem so a fix cannot land unnoticed.

    If stop_confidence is raised, this test should fail and be updated — that is
    the point of it.
    """
    w = weights()
    strong = w.log_odds[EvidenceStrength.STRONG_SUPPORT]
    assert plausibility(strong) > w.stop_confidence
