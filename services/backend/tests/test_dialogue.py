"""Tests for the consultation loop.

Against the synthetic fixture, for the reason given in triage_factories: these
are about the loop, and pinning them to real clinical rows would let an approved
evidence batch break them for reasons that have nothing to do with the code.
"""

from __future__ import annotations

import pytest
from herhealth_contracts.knowledge import UNKNOWN_VALUE, ActionCode, Feature
from triage_factories import build, feature

from herhealth_backend.triage.dialogue import (
    ScriptedAnswers,
    run_consultation,
)
from herhealth_backend.triage.engine import TriageEngine
from herhealth_backend.triage.state import StopReason

# --------------------------------------------------------------------------
# The loop
# --------------------------------------------------------------------------


def test_a_consultation_ends(engine: TriageEngine) -> None:
    transcript = run_consultation(engine, ScriptedAnswers({}))
    assert transcript.final_decision.should_stop


def test_the_last_turn_is_the_conclusion(engine: TriageEngine) -> None:
    transcript = run_consultation(engine, ScriptedAnswers({"pain": "severe"}))
    assert transcript.turns[-1].answer is None
    assert transcript.turns[-1].decision is transcript.final_decision


def test_every_other_turn_carries_an_answer(engine: TriageEngine) -> None:
    transcript = run_consultation(engine, ScriptedAnswers({"pain": "none"}))
    assert all(turn.answer is not None for turn in transcript.turns[:-1])


def test_the_transcript_answers_match_the_final_state(engine: TriageEngine) -> None:
    transcript = run_consultation(engine, ScriptedAnswers({"fever": "yes"}))
    asked = [turn.answer for turn in transcript.turns if turn.answer]
    assert list(transcript.answers) == asked


def test_a_state_is_recorded_before_its_answer_is_applied(engine: TriageEngine) -> None:
    """Each turn holds the state the decision was made FROM.

    The distinction matters for the evaluation harness: explaining why a
    question was chosen requires the scores as they stood when it was chosen,
    not after the answer moved them.
    """
    transcript = run_consultation(engine, ScriptedAnswers({"fever": "yes"}))
    assert transcript.turns[0].state.questions_asked == 0


def test_the_budget_is_respected(engine: TriageEngine) -> None:
    transcript = run_consultation(engine, ScriptedAnswers({}))
    assert transcript.questions_asked <= engine.weights.max_questions


def test_no_feature_is_asked_twice(engine: TriageEngine) -> None:
    transcript = run_consultation(engine, ScriptedAnswers({}))
    asked = [answer.feature_id for answer in transcript.answers]
    assert len(asked) == len(set(asked))


def test_the_same_case_gives_the_same_transcript(engine: TriageEngine) -> None:
    """Determinism is what makes the evaluation harness meaningful."""
    case = ScriptedAnswers({"pain": "severe", "bleeding": "heavy"})
    first = run_consultation(engine, case)
    second = run_consultation(engine, case)
    assert first == second


def test_a_repeating_question_selector_raises_rather_than_hangs() -> None:
    def always_the_same(_: Feature) -> str:
        return UNKNOWN_VALUE

    engine = TriageEngine(build())
    with pytest.raises(RuntimeError, match="repeating itself"):
        run_consultation(engine, always_the_same, hard_limit=0)


# --------------------------------------------------------------------------
# Red flags end it early
# --------------------------------------------------------------------------


def test_a_red_flag_ends_the_consultation(engine: TriageEngine) -> None:
    transcript = run_consultation(engine, ScriptedAnswers({"pain": "severe", "fever": "yes"}))
    assert transcript.final_decision.reason is StopReason.RED_FLAG
    assert transcript.final_decision.action is ActionCode.EMERGENCY


def test_a_red_flag_stops_before_the_budget(engine: TriageEngine) -> None:
    transcript = run_consultation(engine, ScriptedAnswers({"pain": "severe", "fever": "yes"}))
    assert transcript.questions_asked < engine.weights.max_questions


# --------------------------------------------------------------------------
# The user is a lookup, not a script of turns
# --------------------------------------------------------------------------


def test_unlisted_features_come_back_unknown() -> None:
    answers = ScriptedAnswers({"pain": "severe"})
    fever = Feature(**feature("fever", ["yes", "no"]))
    assert answers(fever) == UNKNOWN_VALUE


def test_the_answer_does_not_depend_on_when_it_is_asked() -> None:
    """A case describes a person, so the same question gets the same answer."""
    answers = ScriptedAnswers({"pain": "severe"})
    pain = Feature(**feature("pain", ["none", "mild", "severe"]))
    assert answers(pain) == answers(pain) == "severe"


# --------------------------------------------------------------------------
# Validation — the silent-wrong-answer defence
# --------------------------------------------------------------------------


def features_by_id() -> dict[str, Feature]:
    return build().features_by_id


def test_an_unknown_feature_is_refused() -> None:
    with pytest.raises(ValueError, match="no such feature: 'heavy_bleeding'"):
        ScriptedAnswers.validated({"heavy_bleeding": "yes"}, features_by_id())


def test_a_value_outside_allowed_values_is_refused() -> None:
    """It would otherwise match no row, move nothing, and read as an honest
    unknown — a case meant to escalate coming back routine with no clue why."""
    with pytest.raises(ValueError, match="pain='extreme'"):
        ScriptedAnswers.validated({"pain": "extreme"}, features_by_id())


def test_unknown_is_always_a_legal_answer() -> None:
    ScriptedAnswers.validated({"pain": UNKNOWN_VALUE}, features_by_id())


def test_every_problem_is_reported_at_once() -> None:
    with pytest.raises(ValueError) as caught:
        ScriptedAnswers.validated({"nope": "x", "pain": "extreme"}, features_by_id())
    assert "no such feature" in str(caught.value)
    assert "pain=" in str(caught.value)


def test_a_valid_case_passes() -> None:
    answers = ScriptedAnswers.validated({"pain": "severe"}, features_by_id())
    assert answers.answers == {"pain": "severe"}


# --------------------------------------------------------------------------
# The property the whole design rests on
# --------------------------------------------------------------------------


@pytest.mark.xfail(
    strict=True,
    reason=(
        "KNOWN GAP, found by this test. Stopping rule 4 (CONFIDENT) returns the "
        "TOP condition's action, not the most urgent live one, so a confident "
        "ROUTINE_APPOINTMENT can be returned while an URGENT_SAME_DAY condition "
        "is still above the plausibility floor. Rules 3 and 5 already take the "
        "most urgent; rule 4 does not, and that inconsistency is the bug. "
        "Left failing on purpose rather than patched: changing it makes rule 4 "
        "return the most urgent live baseline in almost every consultation, "
        "which is a policy decision about the over-triage rate and belongs with "
        "the evaluation set, not in a quiet commit. Strict, so it fails loudly "
        "if fixed and this marker is forgotten. See docs/adr/0007."
    ),
)
def test_an_unresolved_differential_never_concludes_below_its_worst_member() -> None:
    """Under-triage is the dominant failure mode, so this is the invariant.

    Whatever the consultation ends up doing, the action it returns must be at
    least as urgent as the most urgent condition it could not eliminate.
    """
    engine = TriageEngine(build())
    transcript = run_consultation(engine, ScriptedAnswers({"bleeding": "heavy"}))
    decision = transcript.final_decision

    severities = {a.code: a.severity for a in engine.base.actions.actions}
    conditions = engine.base.conditions_by_id
    worst = max(
        severities[conditions[c].baseline_action] for c, _ in decision.differential
    )
    assert decision.action is not None
    assert severities[decision.action] >= worst
