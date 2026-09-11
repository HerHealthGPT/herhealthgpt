"""Surviving an invented condition name instead of losing the turn to it.

Two layers, because a bad condition name fails at two different points:
malformed strings never get past ``TriageDecision``'s own validation, and
well-formed-but-unreal ids only fail once there is a knowledge base to check
them against.

The inputs here are verbatim from a live run on 2026-09-11 — the fine-tuned
adapter and the base model, asked about sudden severe pelvic pain with
faintness. Both reached for acute-abdomen diagnoses that this project
deliberately does not model.
"""

from __future__ import annotations

from triage_factories import build

from herhealth_contracts.decision import DecisionType, TriageDecision
from herhealth_backend.triage.provenance import drop_unknown_conditions
from herhealth_backend.triage.vocabulary import (
    ClosedVocabularyViolation,
    validate_against_knowledge_base,
)

#: What the adapter actually returned. Three of the five are not even
#: identifier-shaped, which is what sank the whole decision.
ADAPTER_CONDITIONS = [
    "appendicitis",
    "tubal pregnancy",
    "ovarian cyst torsion",
    "ovarian-cyst rupture",
    "bowel obstruction",
]


def conclude(conditions: list[str]) -> TriageDecision:
    return TriageDecision.model_validate(
        {
            "type": "conclude",
            "action_code": "EMERGENCY",
            "red_flag_id": "severe_pain_with_fever",
            "rationale": "This needs emergency care now.",
            "matching_conditions": conditions,
        }
    )


# -- layer one: malformed names never reach the model at all ----------------


def test_a_name_with_a_space_is_dropped_rather_than_failing_the_decision() -> None:
    decision = conclude(ADAPTER_CONDITIONS)
    # Four of the five carry a space or a hyphen and are dropped. Only
    # "appendicitis" is identifier-shaped, so only it survives this layer —
    # and it is not a real condition either, which layer two handles.
    assert list(decision.matching_conditions) == ["appendicitis"]
    assert decision.action_code is not None
    assert decision.action_code.value == "EMERGENCY"


def test_the_urgency_survives_even_when_every_name_is_malformed() -> None:
    decision = conclude(["tubal pregnancy", "ovarian cyst torsion"])
    assert decision.matching_conditions == ()
    assert decision.action_code is not None
    assert decision.action_code.value == "EMERGENCY"
    assert decision.red_flag_id == "severe_pain_with_fever"


def test_a_well_formed_name_is_left_for_the_second_layer() -> None:
    """This package has no knowledge base, so it must not guess."""
    decision = conclude(["poisoned_oil_poisoning"])
    assert list(decision.matching_conditions) == ["poisoned_oil_poisoning"]


# -- layer two: real ids, checked against conditions.yaml -------------------


def test_an_unreal_condition_is_dropped_and_the_real_ones_kept() -> None:
    base = build()
    decision = drop_unknown_conditions(conclude(["poisoned_oil_poisoning", "infection"]), base)
    assert list(decision.matching_conditions) == ["infection"]


def test_dropping_never_touches_the_action_code_or_the_rule() -> None:
    base = build()
    decision = drop_unknown_conditions(conclude(["appendicitis"]), base)
    assert decision.matching_conditions == ()
    assert decision.action_code is not None
    assert decision.action_code.value == "EMERGENCY"
    assert decision.red_flag_id == "severe_pain_with_fever"


def test_a_decision_with_only_real_conditions_is_returned_unchanged() -> None:
    base = build()
    original = conclude(["infection", "growth"])
    assert drop_unknown_conditions(original, base) is original


def test_the_repaired_decision_passes_the_vocabulary_check() -> None:
    """The point of the whole exercise: no 502, and nothing invented reaches
    the user either."""
    base = build()
    repaired = drop_unknown_conditions(conclude(["poisoned_oil_poisoning", "infection"]), base)
    validate_against_knowledge_base(repaired, base, [])


def test_without_the_repair_the_same_decision_would_have_failed() -> None:
    base = build()
    try:
        validate_against_knowledge_base(conclude(["poisoned_oil_poisoning"]), base, [])
    except ClosedVocabularyViolation as error:
        assert "poisoned_oil_poisoning" in str(error)
    else:  # pragma: no cover - the assertion above is the point
        raise AssertionError("an unreal condition must still fail the check when not repaired")


def test_an_invented_rule_id_is_still_a_hard_failure() -> None:
    """``red_flag_id`` is load-bearing for the urgency itself, so it is
    deliberately NOT repaired — dropping it would leave an escalation
    asserting a rule that does not exist."""
    base = build()
    decision = TriageDecision.model_validate(
        {
            "type": "conclude",
            "action_code": "EMERGENCY",
            "red_flag_id": "severe_pain_with_dizziness",
            "rationale": "This needs emergency care now.",
        }
    )
    repaired = drop_unknown_conditions(decision, base)
    assert repaired.red_flag_id == "severe_pain_with_dizziness"
    try:
        validate_against_knowledge_base(repaired, base, [])
    except ClosedVocabularyViolation as error:
        assert "severe_pain_with_dizziness" in str(error)
    else:  # pragma: no cover
        raise AssertionError("an invented red_flag_id must fail")


def test_a_decline_is_unaffected() -> None:
    base = build()
    decline = TriageDecision(type=DecisionType.DECLINE, rationale="Out of scope.")
    assert drop_unknown_conditions(decline, base) is decline
