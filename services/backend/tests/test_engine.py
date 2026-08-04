"""Tests for the stopping controller.

Every branch of ``should_stop`` has a test, in the order the checks run, because
the order is the policy and a reordering would be a behaviour change that no
individual assertion would catch.

The safety properties get the most attention: red flags outrank everything, an
unresolved differential reports its most urgent member, and concluding
SELF_CARE requires a higher bar than anything else.
"""

from __future__ import annotations

import pytest
from herhealth_contracts.knowledge import UNKNOWN_VALUE, ActionCode
from triage_factories import build, condition, evidence, feature

from herhealth_backend.triage.engine import TriageEngine, most_urgent
from herhealth_backend.triage.state import StopReason

# --------------------------------------------------------------------------
# update
# --------------------------------------------------------------------------


def test_every_condition_starts_at_even_odds(engine: TriageEngine) -> None:
    """Not zero. Before anything is asked, nothing is favoured or excluded."""
    state = engine.initial_state()
    assert set(state.scores) == {"infection", "growth", "normal"}
    assert all(p == pytest.approx(0.5) for p in state.plausibilities().values())


def test_an_answer_adds_the_matching_weight(engine: TriageEngine) -> None:
    state = engine.update(engine.initial_state(), "fever", "yes")
    assert state.scores["infection"] == pytest.approx(1.5)
    assert state.scores["growth"] == pytest.approx(0.0)


def test_argues_against_subtracts(engine: TriageEngine) -> None:
    state = engine.update(engine.initial_state(), "pain", "severe")
    assert state.scores["normal"] < 0
    assert state.scores["infection"] > 0


def test_unknown_moves_nothing(engine: TriageEngine) -> None:
    """`unknown` is weightless, not negative — the user simply did not say."""
    state = engine.update(engine.initial_state(), "fever", UNKNOWN_VALUE)
    assert all(score == pytest.approx(0.0) for score in state.scores.values())


def test_an_unknown_answer_is_still_recorded(engine: TriageEngine) -> None:
    """So the controller does not ask again, and evaluation can tell the
    difference between 'asked and unknown' and 'never asked'."""
    state = engine.update(engine.initial_state(), "fever", UNKNOWN_VALUE)
    assert "fever" in state.asked_feature_ids
    assert state.questions_asked == 1


def test_a_value_with_no_evidence_changes_nothing(engine: TriageEngine) -> None:
    state = engine.update(engine.initial_state(), "bleeding", "light")
    assert all(score == pytest.approx(0.0) for score in state.scores.values())


def test_state_is_immutable(engine: TriageEngine) -> None:
    """A consultation is a list of states, so any of them can be replayed."""
    first = engine.initial_state()
    second = engine.update(first, "fever", "yes")
    assert first.scores["infection"] == pytest.approx(0.0)
    assert second.scores["infection"] == pytest.approx(1.5)


def test_weights_accumulate_across_answers(engine: TriageEngine) -> None:
    state = engine.update(engine.initial_state(), "fever", "yes")
    state = engine.update(state, "pain", "severe")
    assert state.scores["infection"] == pytest.approx(1.5 + 0.6)


# --------------------------------------------------------------------------
# Rule 1 — red flags outrank everything
# --------------------------------------------------------------------------


def test_a_red_flag_stops_immediately(engine: TriageEngine) -> None:
    state = engine.update(engine.initial_state(), "pain", "severe")
    state = engine.update(state, "fever", "yes")
    decision = engine.should_stop(state)
    assert decision.reason is StopReason.RED_FLAG
    assert decision.action is ActionCode.EMERGENCY
    assert decision.red_flag_id == "severe_pain_with_fever"


def test_a_red_flag_needs_every_clause(engine: TriageEngine) -> None:
    """Conjunction only. Half a rule is not a rule."""
    state = engine.update(engine.initial_state(), "pain", "severe")
    assert engine.should_stop(state).reason is not StopReason.RED_FLAG


def test_an_unasked_feature_never_satisfies_a_clause(engine: TriageEngine) -> None:
    state = engine.update(engine.initial_state(), "fever", "yes")
    assert engine.red_flag(state) is None


def test_an_unknown_answer_never_satisfies_a_clause(engine: TriageEngine) -> None:
    """A rule fires on what the user actually said, not on silence."""
    state = engine.update(engine.initial_state(), "pain", "severe")
    state = engine.update(state, "fever", UNKNOWN_VALUE)
    assert engine.red_flag(state) is None


def test_a_red_flag_beats_a_confident_differential(engine: TriageEngine) -> None:
    """Even overwhelming evidence for a benign condition cannot suppress it."""
    state = engine.initial_state()
    for _ in range(3):
        state = engine.update(state, "pain", "none")
    state = engine.update(state, "pain", "severe")
    state = engine.update(state, "fever", "yes")
    assert engine.should_stop(state).reason is StopReason.RED_FLAG


def test_the_decision_names_the_rule(engine: TriageEngine) -> None:
    """So the response can cite the sentence the escalation came from."""
    state = engine.update(engine.initial_state(), "pain", "severe")
    state = engine.update(state, "fever", "yes")
    decision = engine.should_stop(state)
    assert "severe_pain_with_fever" in decision.explanation


# --------------------------------------------------------------------------
# Rule 2 — all live conditions share one action
# --------------------------------------------------------------------------


def test_shared_action_stops() -> None:
    """One condition left means its action is the shared action."""
    base = build(
        conditions=[
            condition("infection", "URGENT_SAME_DAY"),
            condition("growth", "URGENT_SAME_DAY"),
        ],
        rows=[
            evidence("infection", "fever", "yes", "strong_support"),
            evidence("growth", "fever", "yes", "strong_support"),
        ],
        red_flags=[],
    )
    engine = TriageEngine(base)
    decision = engine.should_stop(engine.update(engine.initial_state(), "fever", "yes"))
    assert decision.reason is StopReason.SHARED_ACTION
    assert decision.action is ActionCode.URGENT_SAME_DAY


def test_differing_actions_do_not_stop(engine: TriageEngine) -> None:
    state = engine.update(engine.initial_state(), "pain", "severe")
    assert engine.should_stop(state).reason is not StopReason.SHARED_ACTION


# --------------------------------------------------------------------------
# The SELF_CARE bar — the safety property that matters most
# --------------------------------------------------------------------------


def test_self_care_needs_more_than_a_shared_action() -> None:
    """A weakly supported differential that all means 'nothing to do' must NOT
    conclude self-care. This is the under-triage failure in miniature."""
    base = build(
        conditions=[condition("normal", "SELF_CARE"), condition("variation", "SELF_CARE")],
        rows=[
            evidence("normal", "pain", "none", "weak_support"),
            evidence("variation", "pain", "none", "weak_support"),
        ],
        red_flags=[],
    )
    engine = TriageEngine(base)
    state = engine.update(engine.initial_state(), "pain", "none")
    # weak_support alone is 0.6 log-odds = 0.646, under the 0.85 self-care bar
    assert max(state.plausibilities().values()) < 0.85
    assert engine.should_stop(state).reason is not StopReason.SHARED_ACTION


def test_one_strong_finding_is_not_enough_for_self_care() -> None:
    """0.818 is under the 0.85 bar. Written as a test because it is the single
    most important number in the system: it is what stops the controller
    concluding "nothing to do" on one reassuring answer."""
    base = build(
        conditions=[condition("normal", "SELF_CARE")],
        rows=[evidence("normal", "pain", "none", "strong_support")],
        red_flags=[],
    )
    engine = TriageEngine(base)
    state = engine.update(engine.initial_state(), "pain", "none")
    assert state.plausibilities()["normal"] == pytest.approx(0.818, abs=0.005)
    assert engine.should_stop(state).action is not ActionCode.SELF_CARE


def test_self_care_stops_once_the_higher_bar_is_cleared() -> None:
    """Two strong findings reach 0.953, which clears it."""
    base = build(
        conditions=[condition("normal", "SELF_CARE")],
        rows=[
            evidence("normal", "pain", "none", "strong_support"),
            evidence("normal", "bleeding", "light", "strong_support"),
        ],
        red_flags=[],
    )
    engine = TriageEngine(base)
    state = engine.update(engine.initial_state(), "pain", "none")
    state = engine.update(state, "bleeding", "light")
    assert state.plausibilities()["normal"] > 0.85
    decision = engine.should_stop(state)
    assert decision.action is ActionCode.SELF_CARE


def test_a_non_self_care_shared_action_needs_no_extra_confidence() -> None:
    """Only SELF_CARE carries the higher bar; urgency does not have to be
    proven to the same standard, because erring upward is safe."""
    base = build(
        conditions=[condition("infection", "URGENT_SAME_DAY")],
        rows=[evidence("infection", "pain", "severe", "weak_support")],
        red_flags=[],
    )
    engine = TriageEngine(base)
    state = engine.update(engine.initial_state(), "pain", "severe")
    decision = engine.should_stop(state)
    assert decision.reason is StopReason.SHARED_ACTION
    assert decision.action is ActionCode.URGENT_SAME_DAY


# --------------------------------------------------------------------------
# Rule 3 — nothing left worth asking
# --------------------------------------------------------------------------


def test_stops_when_no_question_could_change_the_action() -> None:
    base = build(
        features=[feature("pain", ["none", "severe"])],
        conditions=[condition("a", "ROUTINE_APPOINTMENT"), condition("b", "URGENT_SAME_DAY")],
        rows=[evidence("a", "pain", "severe", "weak_support")],
        red_flags=[],
    )
    engine = TriageEngine(base)
    state = engine.update(engine.initial_state(), "pain", "severe")
    decision = engine.should_stop(state)
    assert decision.reason is StopReason.NO_INFORMATIVE_QUESTION


def test_that_stop_reports_the_most_urgent_action() -> None:
    """Unresolved differential, so the urgent member wins over the likelier one."""
    base = build(
        features=[feature("pain", ["none", "severe"])],
        conditions=[condition("a", "ROUTINE_APPOINTMENT"), condition("b", "URGENT_SAME_DAY")],
        rows=[evidence("a", "pain", "severe", "strong_support")],
        red_flags=[],
    )
    engine = TriageEngine(base)
    state = engine.update(engine.initial_state(), "pain", "severe")
    decision = engine.should_stop(state)
    assert decision.action is ActionCode.URGENT_SAME_DAY, "must not report the likelier benign one"


# --------------------------------------------------------------------------
# Rule 4 — one condition clearly ahead
# --------------------------------------------------------------------------


def test_a_clear_leader_stops() -> None:
    base = build(
        conditions=[
            condition("infection", "URGENT_SAME_DAY"),
            condition("growth", "ROUTINE_APPOINTMENT"),
        ],
        rows=[evidence("infection", "fever", "yes", "strong_support")],
        red_flags=[],
    )
    engine = TriageEngine(base)
    state = engine.update(engine.initial_state(), "fever", "yes")
    decision = engine.should_stop(state)
    assert decision.reason is StopReason.CONFIDENT
    assert decision.action is ActionCode.URGENT_SAME_DAY


def test_a_narrow_lead_does_not_stop() -> None:
    """stop_margin exists so two neck-and-neck conditions keep the questions
    coming rather than the leader being declared on noise."""
    base = build(
        conditions=[condition("a", "URGENT_SAME_DAY"), condition("b", "ROUTINE_APPOINTMENT")],
        rows=[
            evidence("a", "fever", "yes", "strong_support"),
            evidence("b", "fever", "yes", "strong_support"),
            evidence("a", "bleeding", "heavy", "weak_support"),
        ],
        red_flags=[],
    )
    engine = TriageEngine(base)
    state = engine.update(engine.initial_state(), "fever", "yes")
    assert engine.should_stop(state).reason is not StopReason.CONFIDENT


# --------------------------------------------------------------------------
# Rule 5 — the question budget
# --------------------------------------------------------------------------


def test_the_budget_ends_the_consultation() -> None:
    weights = dict(
        log_odds={
            "strong_support": 1.5, "weak_support": 0.6, "neutral": 0.0,
            "argues_against": -0.5, "rules_out": -4.0,
        },
        plausibility_floor=0.05, stop_confidence=0.99,
        self_care_stop_confidence=0.999, stop_margin=0.9, max_questions=2,
    )
    base = build(
        conditions=[condition("a", "URGENT_SAME_DAY"), condition("b", "ROUTINE_APPOINTMENT")],
        rows=[
            evidence("a", "fever", "yes", "weak_support"),
            evidence("b", "bleeding", "heavy", "weak_support"),
            evidence("a", "pain", "severe", "weak_support"),
        ],
        red_flags=[],
        weights=weights,
    )
    engine = TriageEngine(base)
    state = engine.initial_state()
    for feature_id, value in [("fever", "yes"), ("bleeding", "heavy")]:
        state = engine.update(state, feature_id, value)
    decision = engine.should_stop(state)
    assert decision.reason is StopReason.MAX_QUESTIONS
    assert decision.action is ActionCode.URGENT_SAME_DAY, "most urgent, not most likely"
    assert decision.differential, "the differential must be reported, not swallowed"


# --------------------------------------------------------------------------
# Rule 6 — otherwise ask
# --------------------------------------------------------------------------


def test_asks_when_nothing_is_settled(engine: TriageEngine) -> None:
    decision = engine.should_stop(engine.initial_state())
    assert decision.reason is StopReason.ASK
    assert decision.next_feature_id is not None
    assert not decision.should_stop


def test_a_question_is_never_repeated(engine: TriageEngine) -> None:
    state = engine.initial_state()
    asked: list[str] = []
    for _ in range(4):
        decision = engine.should_stop(state)
        if decision.reason is not StopReason.ASK or decision.next_feature_id is None:
            break
        asked.append(decision.next_feature_id)
        state = engine.update(state, decision.next_feature_id, UNKNOWN_VALUE)
    assert len(asked) == len(set(asked))


# --------------------------------------------------------------------------
# next_question
# --------------------------------------------------------------------------


def test_burden_is_traded_against_separation(engine: TriageEngine) -> None:
    """The most intrusive question must not be asked first just because it
    happens to be informative."""
    first = engine.should_stop(engine.initial_state()).next_feature_id
    assert first != "private_question"


def test_a_feature_no_live_condition_uses_is_not_asked() -> None:
    base = build(
        features=[feature("pain", ["none", "severe"]), feature("irrelevant", ["yes", "no"])],
        conditions=[condition("a", "ROUTINE_APPOINTMENT")],
        rows=[evidence("a", "pain", "severe", "weak_support")],
        red_flags=[],
    )
    engine = TriageEngine(base)
    assert engine.next_question(engine.initial_state()) == "pain"


def test_a_red_flag_feature_is_always_worth_asking() -> None:
    """Even with no evidence rows, because a red flag can escalate regardless
    of what the differential thinks."""
    base = build(
        features=[feature("pain", ["none", "severe"]), feature("shoulder", ["yes", "no"])],
        conditions=[condition("a", "ROUTINE_APPOINTMENT")],
        rows=[evidence("a", "pain", "severe", "weak_support")],
        red_flags=[
            {
                "id": "shoulder_tip",
                "label": "Shoulder tip pain",
                "all_of": [{"feature_id": "shoulder", "op": "equals", "value": "yes"}],
                "action": "EMERGENCY",
                "source_id": "src_a",
                "source_quote": "Call for help if you have shoulder tip pain.",
            }
        ],
    )
    engine = TriageEngine(base)
    state = engine.update(engine.initial_state(), "pain", "severe")
    assert engine.next_question(state) == "shoulder"


def test_selection_is_deterministic(engine: TriageEngine) -> None:
    """Same state, same question — otherwise a replayed consultation diverges."""
    state = engine.initial_state()
    assert engine.next_question(state) == engine.next_question(state)


# --------------------------------------------------------------------------
# most_urgent
# --------------------------------------------------------------------------


def test_most_urgent_picks_the_highest_severity() -> None:
    assert most_urgent([ActionCode.SELF_CARE, ActionCode.EMERGENCY]) is ActionCode.EMERGENCY
    assert (
        most_urgent([ActionCode.ROUTINE_APPOINTMENT, ActionCode.URGENT_SAME_DAY])
        is ActionCode.URGENT_SAME_DAY
    )


def test_most_urgent_of_nothing_is_nothing() -> None:
    assert most_urgent([]) is None
