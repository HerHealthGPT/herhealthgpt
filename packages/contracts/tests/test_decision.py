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


def test_a_red_flag_conclusion_below_urgent_may_not_name_conditions() -> None:
    """The general rule: red flags escalate on a symptom pattern without
    asserting what it is — the discipline CLAUDE.md applies to cancer,
    generalised by ADR 0011.

    The exception widened on 2026-09-17 from EMERGENCY alone to both urgent
    tiers, so the boundary this guards is now between ROUTINE_APPOINTMENT and
    URGENT_SAME_DAY rather than between URGENT_SAME_DAY and EMERGENCY.
    """
    with pytest.raises(ValidationError, match="must not name matching_conditions"):
        TriageDecision(
            type=DecisionType.CONCLUDE,
            action_code=ActionCode.ROUTINE_APPOINTMENT,
            red_flag_id="severe_pelvic_pain",
            matching_conditions=("pelvic_inflammatory_disease",),
            rationale="testing",
        )


def test_an_urgent_same_day_red_flag_may_name_conditions() -> None:
    """Widened 2026-09-17 on the product owner's decision: a woman told to be
    seen today is making the same "what is this about?" judgement as one sent
    to an emergency department. Still "may match patterns our sources
    associate with…", never "you have…"."""
    decision = TriageDecision(
        type=DecisionType.CONCLUDE,
        action_code=ActionCode.URGENT_SAME_DAY,
        red_flag_id="severe_pelvic_pain",
        matching_conditions=("pelvic_inflammatory_disease",),
        rationale="testing",
    )
    assert decision.matching_conditions == ("pelvic_inflammatory_disease",)


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


def test_an_inform_answers_from_its_citations() -> None:
    """The shape ADR 0016 added: an in-scope question about the subject,
    answered from retrieved passages, with no urgency attached."""
    decision = TriageDecision(
        type=DecisionType.INFORM,
        answer_text="PCOS affects how the ovaries work, our sources say.",
        citations=(A_PASSAGE_ID,),
        observed={"cycle_regularity": "irregular"},
        rationale="She asked what the condition is, having reported no symptom.",
    )
    assert decision.action_code is None
    assert decision.matching_conditions == ()
    # Allowed here and forbidden on a DECLINE, deliberately: an in-scope
    # question may mention a real feature value in passing, and recording it
    # is what lets the next turn carry on from it.
    assert decision.observed == {"cycle_regularity": "irregular"}


def test_an_inform_must_cite_something() -> None:
    """Stricter than ASK and CONCLUDE, not looser: there is no red_flag_id
    route to grounding an informational answer, because a warning sign is a
    reason to escalate rather than a reason to explain."""
    with pytest.raises(ValidationError, match="must cite at least one"):
        TriageDecision(
            type=DecisionType.INFORM,
            answer_text="PCOS affects how the ovaries work.",
            rationale="testing",
        )


def test_an_inform_always_ends_up_with_an_answer() -> None:
    """``answer_text`` is what every consumer renders and asserts on, so an
    INFORM without one must be unconstructible. In practice the promotion
    below gets there first — ``rationale`` is itself required, so there is no
    payload that reaches the ``requires answer_text`` guard. That guard is
    the backstop behind the promotion, not a path a model can hit, and this
    test pins the invariant rather than the branch."""
    decision = TriageDecision(
        type=DecisionType.INFORM,
        citations=(A_PASSAGE_ID,),
        rationale="PCOS affects how the ovaries work.",
    )
    assert decision.answer_text == "PCOS affects how the ovaries work."


def test_an_inform_promotes_a_rationale_into_a_missing_answer() -> None:
    """A model that found the right shape and filled the wrong field of it is
    one correction away, and a corrective retry costs a whole generation —
    see the coercion's own note in decision.py."""
    decision = TriageDecision.model_validate(
        {
            "type": "inform",
            "citations": [A_PASSAGE_ID],
            "rationale": "Endometriosis is tissue similar to the womb lining.",
        }
    )
    assert decision.answer_text == "Endometriosis is tissue similar to the womb lining."


@pytest.mark.parametrize(
    ("field", "value"),
    [
        # No urgency level, so an informational answer can never double as
        # reassurance.
        ("action_code", ActionCode.SELF_CARE),
        # A noticed warning sign must escalate, not explain.
        ("red_flag_id", "severe_pelvic_pain"),
        # Nothing was matched against her — she described no case. This is
        # what keeps "never diagnoses" structural on this path.
        ("matching_conditions", ("pcos",)),
        ("question_text", "Are you pregnant?"),
        ("next_feature_id", "pregnancy_status"),
    ],
)
def test_an_inform_may_carry_nothing_but_its_answer(field: str, value: object) -> None:
    with pytest.raises(ValidationError, match="must not carry"):
        TriageDecision(
            type=DecisionType.INFORM,
            answer_text="PCOS affects how the ovaries work.",
            citations=(A_PASSAGE_ID,),
            rationale="testing",
            **{field: value},  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("decision_type", [DecisionType.ASK, DecisionType.CONCLUDE])
def test_answer_text_is_only_legal_on_an_inform(decision_type: DecisionType) -> None:
    """An ask carries question_text and a conclude carries rationale; a long
    answer on either would be text no part of the UI renders."""
    shape: dict[str, object] = {
        DecisionType.ASK: {
            "next_feature_id": "pregnancy_status",
            "question_text": "Are you pregnant?",
        },
        DecisionType.CONCLUDE: {"action_code": ActionCode.ROUTINE_APPOINTMENT},
    }[decision_type]
    with pytest.raises(ValidationError, match="only legal on an INFORM"):
        TriageDecision(
            type=decision_type,
            answer_text="PCOS affects how the ovaries work.",
            citations=(A_PASSAGE_ID,),
            rationale="testing",
            **shape,  # type: ignore[arg-type]
        )
