"""The more severe warning signs listed beside a warning-sign conclusion."""

from __future__ import annotations

from pathlib import Path

import pytest
from herhealth_contracts.decision import DecisionType, TriageDecision
from herhealth_contracts.knowledge import ActionCode, KnowledgeBase
from herhealth_contracts.loading import load_knowledge_base

from herhealth_backend.app.triage.routes import _emergency_signs

REPO = Path(__file__).resolve().parents[4]
FEVER = {"pelvic_pain_severity": "moderate", "fever": "yes"}


@pytest.fixture(scope="module")
def base() -> KnowledgeBase:
    return load_knowledge_base(REPO / "knowledge")


def _conclude(action: str, red_flag: str | None) -> TriageDecision:
    return TriageDecision(
        type=DecisionType.CONCLUDE,
        action_code=ActionCode(action),
        red_flag_id=red_flag,
        rationale="testing",
        citations=() if red_flag else ("a6bf0793b2a9a509",),
    )


def test_a_same_day_warning_sign_lists_the_emergencies_one_answer_away(
    base: KnowledgeBase,
) -> None:
    signs = _emergency_signs(
        _conclude("URGENT_SAME_DAY", "pelvic_pain_with_fever"), base, FEVER, []
    )
    ids = {sign["rule_id"] for sign in signs}
    assert "pelvic_pain_with_faintness" in ids
    assert all(sign["action"] == "EMERGENCY" for sign in signs)


def test_a_sign_already_asked_about_is_not_listed(base: KnowledgeBase) -> None:
    answers = {**FEVER, "feeling_faint": "no"}
    signs = _emergency_signs(
        _conclude("URGENT_SAME_DAY", "pelvic_pain_with_fever"), base, answers, ["feeling_faint"]
    )
    assert "pelvic_pain_with_faintness" not in {sign["rule_id"] for sign in signs}


@pytest.mark.parametrize(
    ("action", "red_flag"),
    [("EMERGENCY", "pelvic_pain_with_faintness"), ("ROUTINE_APPOINTMENT", None)],
)
def test_nothing_is_listed_at_emergency_or_without_a_warning_sign(
    base: KnowledgeBase, action: str, red_flag: str | None
) -> None:
    answers = {**FEVER, "feeling_faint": "yes"} if red_flag else FEVER
    assert _emergency_signs(_conclude(action, red_flag), base, answers, []) == []
