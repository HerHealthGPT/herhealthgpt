"""Tests for the evaluation metrics.

The property under test throughout is that a number is never more flattering
than the evidence for it. Two specific ways that could go wrong, both with a
precedent in the study that motivated this architecture:

- An aggregate that hides a safety failure. Risk accuracy 0.667 sat above a
  0.644 baseline while English under-triage was 0.718.
- A rate computed over an empty denominator printing as though it passed.
"""

from __future__ import annotations

import pytest
from herhealth_contracts.evaluation import Language, RegisterStyle
from herhealth_contracts.knowledge import ActionCode

from herhealth_backend.evaluation.metrics import CaseOutcome, score

SELF = ActionCode.SELF_CARE
ROUTINE = ActionCode.ROUTINE_APPOINTMENT
URGENT = ActionCode.URGENT_SAME_DAY
EMERGENCY = ActionCode.EMERGENCY


def outcome(
    case_id: str = "c1",
    *,
    expected: ActionCode = ROUTINE,
    predicted: ActionCode = ROUTINE,
    language: Language = Language.EN,
    style: RegisterStyle = RegisterStyle.CANONICAL,
    expected_red_flag: str = "",
    fired_red_flag: str | None = None,
    needs_clarification: bool = False,
    asked: bool = False,
    questions: int = 3,
) -> CaseOutcome:
    return CaseOutcome(
        canonical_case_id=case_id,
        language=language,
        style=style,
        expected_action=expected,
        predicted_action=predicted,
        expected_red_flag_id=expected_red_flag,
        fired_red_flag_id=fired_red_flag,
        needs_clarification=needs_clarification,
        asked_a_question=asked,
        questions_asked=questions,
    )


# --------------------------------------------------------------------------
# Direction — under-triage and over-triage are not symmetric
# --------------------------------------------------------------------------


def test_a_less_urgent_answer_is_under_triage() -> None:
    assert outcome(expected=URGENT, predicted=ROUTINE).under_triaged


def test_a_more_urgent_answer_is_over_triage_not_under() -> None:
    result = outcome(expected=ROUTINE, predicted=URGENT)
    assert result.over_triaged
    assert not result.under_triaged


def test_the_two_are_counted_separately() -> None:
    metrics = score(
        [
            outcome("a", expected=URGENT, predicted=ROUTINE),
            outcome("b", expected=ROUTINE, predicted=EMERGENCY),
        ]
    )
    assert metrics.under_triage_rate == pytest.approx(0.5)
    assert metrics.over_triage_rate == pytest.approx(0.5)


def test_only_under_triage_gates() -> None:
    """Over-triage is a cost this design accepts. It must not block a merge."""
    metrics = score([outcome(expected=SELF, predicted=EMERGENCY)])
    assert metrics.over_triage_rate == pytest.approx(1.0)
    assert not any("over-triage" in f for f in metrics.gated_failures())


def test_a_self_care_label_cannot_be_under_triaged() -> None:
    """Nothing is less urgent, so it must not sit in the denominator and
    flatter the rate."""
    metrics = score([outcome(expected=SELF, predicted=SELF)])
    assert metrics.under_triage_rate is None


# --------------------------------------------------------------------------
# Unmeasured is not zero, and not a pass
# --------------------------------------------------------------------------


def test_a_rate_over_nothing_is_none_not_zero() -> None:
    assert score([outcome(expected=SELF)]).under_triage_rate is None


def test_red_flag_recall_over_no_red_flag_cases_is_unmeasured() -> None:
    """The most dangerous number this system could print is a red-flag recall
    of 1.000 computed over zero red-flag cases."""
    assert score([outcome()]).red_flag_recall is None


def test_unmeasured_red_flag_recall_fails_the_gate() -> None:
    failures = score([outcome()]).gated_failures()
    assert any("red-flag recall is unmeasured" in f for f in failures)


def test_unmeasured_clarification_recall_fails_the_gate() -> None:
    failures = score([outcome()]).gated_failures()
    assert any("clarification recall is unmeasured" in f for f in failures)


def test_an_empty_run_passes_no_gate() -> None:
    assert score([]).gated_failures()


# --------------------------------------------------------------------------
# Red-flag recall — the rule must be the right rule
# --------------------------------------------------------------------------


def test_the_right_rule_firing_is_a_hit() -> None:
    metrics = score(
        [
            outcome(
                expected=EMERGENCY,
                predicted=EMERGENCY,
                expected_red_flag="r1",
                fired_red_flag="r1",
            )
        ]
    )
    assert metrics.red_flag_recall == pytest.approx(1.0)


def test_the_wrong_rule_firing_is_a_miss() -> None:
    """A rule firing for the wrong reason is not recall. It reached the right
    action by luck, and the reason cited to the user would be wrong."""
    metrics = score(
        [
            outcome(
                expected=EMERGENCY,
                predicted=EMERGENCY,
                expected_red_flag="r1",
                fired_red_flag="r2",
            )
        ]
    )
    assert metrics.red_flag_recall == pytest.approx(0.0)


def test_no_rule_firing_is_a_miss() -> None:
    metrics = score([outcome(expected=EMERGENCY, expected_red_flag="r1", fired_red_flag=None)])
    assert metrics.red_flag_recall == pytest.approx(0.0)


def test_recall_below_one_fails_the_gate() -> None:
    metrics = score(
        [
            outcome("a", expected=EMERGENCY, expected_red_flag="r1", fired_red_flag="r1"),
            outcome("b", expected=EMERGENCY, expected_red_flag="r2", fired_red_flag=None),
        ]
    )
    assert metrics.red_flag_recall == pytest.approx(0.5)
    assert any("red-flag recall" in f and "below 1.0" in f for f in metrics.gated_failures())


# --------------------------------------------------------------------------
# Per language — the asymmetry that was missed last time
# --------------------------------------------------------------------------


def test_under_triage_is_reported_per_language() -> None:
    metrics = score(
        [
            outcome("a", expected=URGENT, predicted=URGENT, language=Language.EN),
            outcome("b", expected=URGENT, predicted=ROUTINE, language=Language.FR),
        ]
    )
    assert metrics.under_triage_by_language[Language.EN] == pytest.approx(0.0)
    assert metrics.under_triage_by_language[Language.FR] == pytest.approx(1.0)


def test_one_bad_language_fails_the_gate_even_when_the_aggregate_looks_fine() -> None:
    """The exact shape of the original failure: French under-triage at 0.994
    while the aggregate stayed respectable."""
    outcomes = [
        outcome(f"en{i}", expected=URGENT, predicted=URGENT, language=Language.EN)
        for i in range(20)
    ]
    outcomes.append(outcome("fr1", expected=URGENT, predicted=ROUTINE, language=Language.FR))
    metrics = score(outcomes)
    assert metrics.under_triage_rate is not None and metrics.under_triage_rate < 0.05
    assert any("under-triage in fr" in f for f in metrics.gated_failures())


# --------------------------------------------------------------------------
# Clarification
# --------------------------------------------------------------------------


def test_asking_on_an_ambiguous_case_is_recall() -> None:
    metrics = score([outcome(needs_clarification=True, asked=True)])
    assert metrics.clarification_recall == pytest.approx(1.0)


def test_concluding_on_an_ambiguous_case_is_a_miss() -> None:
    metrics = score([outcome(needs_clarification=True, asked=False)])
    assert metrics.clarification_recall == pytest.approx(0.0)


def test_cases_not_needing_clarification_are_not_in_the_denominator() -> None:
    metrics = score(
        [
            outcome("a", needs_clarification=True, asked=True),
            outcome("b", needs_clarification=False, asked=False),
        ]
    )
    assert metrics.clarification_cases == 1
    assert metrics.clarification_recall == pytest.approx(1.0)


# --------------------------------------------------------------------------
# Agreement — consistency is not a safety metric
# --------------------------------------------------------------------------


def test_agreement_needs_more_than_one_variant_to_mean_anything() -> None:
    """At controller level every case runs once from feature values, so
    agreement would be a guaranteed 1.0 measuring nothing."""
    assert score([outcome()]).cross_language_action_agreement is None


def test_variants_agreeing_counts_as_agreement() -> None:
    metrics = score(
        [
            outcome("a", predicted=URGENT, language=Language.EN),
            outcome("a", predicted=URGENT, language=Language.FR),
        ]
    )
    assert metrics.cross_language_action_agreement == pytest.approx(1.0)


def test_variants_disagreeing_counts_against() -> None:
    metrics = score(
        [
            outcome("a", predicted=URGENT, language=Language.EN),
            outcome("a", predicted=ROUTINE, language=Language.FR),
        ]
    )
    assert metrics.cross_language_action_agreement == pytest.approx(0.0)


def test_perfect_agreement_can_coexist_with_total_under_triage() -> None:
    """THE warning this metric carries. Cross-language consistency improved in
    the original study while the model collapsed onto one answer for every
    case. A high agreement number beside a high under-triage number means the
    system is uniformly wrong, and the report must show both."""
    metrics = score(
        [
            outcome("a", expected=URGENT, predicted=ROUTINE, language=Language.EN),
            outcome("a", expected=URGENT, predicted=ROUTINE, language=Language.FR),
        ]
    )
    assert metrics.cross_language_action_agreement == pytest.approx(1.0)
    assert metrics.under_triage_rate == pytest.approx(1.0)
    assert metrics.gated_failures()


def test_register_agreement_is_measured_separately_from_language() -> None:
    metrics = score(
        [
            outcome("a", predicted=URGENT, style=RegisterStyle.CANONICAL),
            outcome("a", predicted=ROUTINE, style=RegisterStyle.AMBIGUOUS),
        ]
    )
    assert metrics.register_action_agreement == pytest.approx(0.0)
    assert metrics.cross_language_action_agreement is None


# --------------------------------------------------------------------------
# Bookkeeping
# --------------------------------------------------------------------------


def test_out_of_scope_cases_are_counted_not_hidden() -> None:
    """A gap we chose is not a gap we missed, and the report must say which."""
    assert score([outcome()], out_of_scope=30).cases_out_of_scope == 30


def test_mean_questions_is_reported() -> None:
    metrics = score([outcome("a", questions=2), outcome("b", questions=4)])
    assert metrics.mean_questions_asked == pytest.approx(3.0)


def test_exact_agreement_is_reported_but_does_not_gate() -> None:
    metrics = score([outcome(expected=URGENT, predicted=ROUTINE)])
    assert metrics.exact_action_agreement == pytest.approx(0.0)
    assert not any("exact" in f for f in metrics.gated_failures())
