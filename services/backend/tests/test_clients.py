"""Unit tests for reasoning clients — connectivity fallback and parsing."""

from __future__ import annotations

import json

import pytest
from herhealth_contracts.decision import DecisionType, TriageDecision
from herhealth_contracts.knowledge import ActionCode

from herhealth_backend.triage.clients import (
    _parse_chat_completion_payload,
    _reject_leaked_internals,
    _strip_thinking_blocks,
)

_VALID_DECISION = TriageDecision(
    type=DecisionType.ASK,
    next_feature_id="pregnancy_status",
    question_text="Are you pregnant?",
    citations=("0123456789abcdef",),
    rationale="testing",
)

_VALID_PAYLOAD = {
    "choices": [
        {
            "message": {
                "content": json.dumps(
                    {
                        "type": "ask",
                        "next_feature_id": "pregnancy_status",
                        "question_text": "Are you pregnant?",
                        "citations": ["0123456789abcdef"],
                        "rationale": "testing",
                    }
                )
            }
        }
    ]
}


def test_strip_thinking_blocks_removes_redacted_block() -> None:
    raw = (
        '<think>internal</think>'
        '{"type":"ask","rationale":"x","next_feature_id":"pregnancy_status",'
        '"question_text":"?","citations":["a"]}'
    )
    assert _strip_thinking_blocks(raw).startswith('{"type"')


def test_parse_chat_completion_payload_validates_decision() -> None:
    decision = _parse_chat_completion_payload(_VALID_PAYLOAD)
    assert decision.type is DecisionType.ASK
    assert decision.next_feature_id == "pregnancy_status"


@pytest.mark.parametrize(
    "rationale",
    [
        "Please go to an emergency room now or call your local emergency number.",
        "This is a medical emergency — do not wait.",
        "Bleeding in pregnancy is best checked right away.",
        "Heavy bleeding with faintness needs same-day care.",
    ],
)
def test_reject_leaked_internals_allows_ordinary_english(rationale: str) -> None:
    """The words a real answer needs must not trip the guard. "emergency room"
    is the correct thing to say; only the all-caps code is machine leakage.
    """
    _reject_leaked_internals(
        TriageDecision(
            type=DecisionType.CONCLUDE,
            action_code=ActionCode.EMERGENCY,
            citations=("0123456789abcdef",),
            rationale=rationale,
        )
    )


@pytest.mark.parametrize(
    "rationale",
    [
        "This matches a red-flag warning: pelvic pain with faintness or collapse",
        "CODE EMERGENCY",
        "action_code: URGENT_SAME_DAY",
        "matched red_flag_id pelvic_pain_with_fever",
        "see passage_id a6bf0793b2a9a509 for details",
        "I set matching_conditions to endometriosis",
    ],
)
def test_reject_leaked_internals_flags_machine_text(rationale: str) -> None:
    """Every string here is text this system actually produced, or a direct
    variant of it. ``rationale`` is rendered to the user verbatim, so these
    must fail validation and be retried rather than displayed.
    """
    with pytest.raises(ValueError, match="internal machinery"):
        _reject_leaked_internals(
            TriageDecision(
                type=DecisionType.CONCLUDE,
                action_code=ActionCode.EMERGENCY,
                citations=("0123456789abcdef",),
                rationale=rationale,
            )
        )


def test_reject_leaked_internals_checks_question_text_too() -> None:
    with pytest.raises(ValueError, match="question_text"):
        _reject_leaked_internals(
            TriageDecision(
                type=DecisionType.ASK,
                next_feature_id="pregnancy_status",
                question_text="To check the red flag rule, are you pregnant?",
                citations=("0123456789abcdef",),
                rationale="Checking whether pregnancy applies.",
            )
        )


def test_names_beside_a_same_day_red_flag_are_dropped_not_the_turn() -> None:
    """ADR 0013, narrowed back 2026-10-19: only EMERGENCY may name conditions
    beside a red flag. A same-day reply that names them keeps its urgency and
    its rule; only the names go."""
    from herhealth_backend.triage.clients import parse_decision_text

    decision = parse_decision_text(
        '{"type": "conclude", "action_code": "URGENT_SAME_DAY", '
        '"red_flag_id": "severe_pelvic_pain", '
        '"matching_conditions": ["pelvic_inflammatory_disease"], '
        '"rationale": "Pain this severe needs to be seen today.", "citations": []}'
    )
    assert decision.action_code is not None
    assert decision.action_code.value == "URGENT_SAME_DAY"
    assert decision.red_flag_id == "severe_pelvic_pain"
    assert decision.matching_conditions == ()


def test_names_beside_an_emergency_red_flag_are_kept() -> None:
    from herhealth_backend.triage.clients import parse_decision_text

    decision = parse_decision_text(
        '{"type": "conclude", "action_code": "EMERGENCY", '
        '"red_flag_id": "severe_pelvic_pain", '
        '"matching_conditions": ["ovarian_cyst"], '
        '"rationale": "Go to an emergency department now.", "citations": []}'
    )
    assert decision.matching_conditions == ("ovarian_cyst",)
