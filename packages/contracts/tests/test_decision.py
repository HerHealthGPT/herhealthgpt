"""``TriageDecision``'s shape rules — the one deterministic safety net left.

First test coverage this model has had; written alongside the 2026-09-02
product decision (ADR 0013) that narrowed the red-flag/condition-naming
rule, so both the rule and its one deliberate exception are pinned.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from herhealth_contracts.decision import DecisionType, TriageDecision
from herhealth_contracts.knowledge import ActionCode

A_PASSAGE_ID = "0123456789abcdef"


def test_a_decision_grounded_in_nothing_is_refused() -> None:
    with pytest.raises(ValidationError, match="grounded"):
        TriageDecision(
            type=DecisionType.CONCLUDE,
            action_code=ActionCode.ROUTINE_APPOINTMENT,
            rationale="testing",
        )


def test_an_ask_requires_a_feature_and_a_question() -> None:
    with pytest.raises(ValidationError, match="next_feature_id and question_text"):
        TriageDecision(
            type=DecisionType.ASK,
            citations=(A_PASSAGE_ID,),
            rationale="testing",
        )


def test_a_red_flag_conclusion_below_emergency_may_not_name_conditions() -> None:
    """The general rule, unchanged: red flags escalate on a symptom pattern
    without asserting what it is — the discipline CLAUDE.md applies to
    cancer, generalised by ADR 0011."""
    with pytest.raises(ValidationError, match="must not name matching_conditions"):
        TriageDecision(
            type=DecisionType.CONCLUDE,
            action_code=ActionCode.URGENT_SAME_DAY,
            red_flag_id="severe_pelvic_pain",
            matching_conditions=("pelvic_inflammatory_disease",),
            rationale="testing",
        )


def test_an_emergency_red_flag_conclusion_may_name_conditions() -> None:
    """The one deliberate exception (product decision, 2026-09-02, ADR
    0013): at EMERGENCY, naming the matching patterns alongside the red
    flag is allowed."""
    decision = TriageDecision(
        type=DecisionType.CONCLUDE,
        action_code=ActionCode.EMERGENCY,
        red_flag_id="sudden_severe_pelvic_pain",
        matching_conditions=("ovarian_cyst",),
        rationale="testing",
    )
    assert decision.matching_conditions == ("ovarian_cyst",)


def test_null_matching_conditions_coerces_to_empty_tuple() -> None:
    """OpenRouter emits null for empty arrays — must not 502 the turn."""
    decision = TriageDecision.model_validate(
        {
            "type": "ask",
            "next_feature_id": "pregnancy_status",
            "question_text": "Are you pregnant?",
            "matching_conditions": None,
            "citations": [A_PASSAGE_ID],
            "rationale": "testing",
        }
    )
    assert decision.matching_conditions == ()


def test_passage_id_prefix_on_citations_is_stripped() -> None:
    """Models copy ``passage_id=…`` from the retrieval prompt into citations;
    accepting the bare hash avoids a full OpenRouter retry (~10–60s)."""
    decision = TriageDecision.model_validate(
        {
            "type": "ask",
            "next_feature_id": "pregnancy_status",
            "question_text": "Are you pregnant?",
            "citations": [f"passage_id={A_PASSAGE_ID}", f"passage_id={A_PASSAGE_ID}"],
            "rationale": "testing",
        }
    )
    assert decision.citations == (A_PASSAGE_ID, A_PASSAGE_ID)


def test_a_red_flag_alone_still_grounds_a_decision() -> None:
    """A red-flag-driven decision with no citations stays valid — red flags
    are injected, never retrieved, so there is nothing to cite (the reason
    red_flag_id exists at all — see decision.py's docstring)."""
    decision = TriageDecision(
        type=DecisionType.CONCLUDE,
        action_code=ActionCode.EMERGENCY,
        red_flag_id="sudden_severe_pelvic_pain",
        rationale="testing",
    )
    assert decision.citations == ()
