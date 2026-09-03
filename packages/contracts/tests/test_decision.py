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


def test_a_decline_needs_no_grounding() -> None:
    """The one exemption from the grounding rule, and the reason DECLINE
    exists: requiring a citation for a refusal is what made the model attach
    a blood-count quote to "who won world cup 2026" (ADR 0014)."""
    decision = TriageDecision(
        type=DecisionType.DECLINE,
        rationale="This tool covers women's reproductive health only.",
    )
    assert decision.citations == ()
    assert decision.action_code is None


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("action_code", ActionCode.SELF_CARE),
        ("citations", (A_PASSAGE_ID,)),
        ("matching_conditions", ("pcos",)),
        ("red_flag_id", "severe_pelvic_pain"),
        ("question_text", "Are you pregnant?"),
        ("next_feature_id", "pregnancy_status"),
    ],
)
def test_a_decline_may_carry_nothing_but_its_rationale(field: str, value: object) -> None:
    """Forbidden, not merely optional — "declined *and* assigned an urgency"
    must be unconstructible, and a refusal must not be able to smuggle in a
    citation for something it never assessed."""
    with pytest.raises(ValidationError, match="must not carry"):
        TriageDecision(
            type=DecisionType.DECLINE,
            rationale="testing",
            **{field: value},  # type: ignore[arg-type]
        )


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
