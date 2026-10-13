"""The agent's use of the grounding layer: what reaches the prompt, and what
carries between turns.

``test_context.py`` covers the join and the clause arithmetic in isolation.
This file covers the wiring — that ``run_turn`` puts the block in the system
prompt at all, and that ``run_consultation`` accumulates the case vector
rather than rebuilding it from nothing each turn.
"""

from __future__ import annotations

from collections.abc import Sequence

from herhealth_contracts.decision import DecisionType, TriageDecision
from herhealth_contracts.retrieval import PassageType, RetrievedPassage
from triage_factories import build

from herhealth_backend.triage.agent import (
    Message,
    ReasoningResult,
    ScriptedReasoningClient,
    TriageAgent,
)

PASSAGE = RetrievedPassage(
    id="a6bf0793b2a9a509",
    passage_type=PassageType.SOURCE_PASSAGE,
    source_id="src_a",
    text="Some retrieved prose about pain.",
    citation="src_a/doc",
    score=0.5,
)


class StubRetrieval:
    def search(self, query: str, *, k: int = 8) -> list[RetrievedPassage]:
        return [PASSAGE]


class CapturingReasoning:
    """Records the system prompt it was handed, then replays a scripted decision."""

    name = "capturing"

    def __init__(self, decisions: Sequence[TriageDecision]) -> None:
        self.prompts: list[str] = []
        self._inner = ScriptedReasoningClient(decisions, name=self.name)

    def decide(
        self,
        *,
        system_prompt: str,
        history: Sequence[Message],
        context: Sequence[RetrievedPassage],
    ) -> ReasoningResult:
        self.prompts.append(system_prompt)
        return self._inner.decide(system_prompt=system_prompt, history=history, context=context)


def ask(feature_id: str, **observed: str) -> TriageDecision:
    return TriageDecision(
        type=DecisionType.ASK,
        next_feature_id=feature_id,
        question_text=f"What about {feature_id}?",
        citations=(PASSAGE.id,),
        rationale="Because I need to know.",
        observed=observed,
    )


def conclude(**observed: str) -> TriageDecision:
    return TriageDecision(
        type=DecisionType.CONCLUDE,
        action_code="EMERGENCY",
        red_flag_id="severe_pain_with_fever",
        rationale="This needs emergency care now.",
        observed=observed,
    )


def agent_with(*decisions: TriageDecision) -> tuple[TriageAgent, CapturingReasoning]:
    reasoning = CapturingReasoning(decisions)
    return (
        TriageAgent(base=build(), reasoning=reasoning, retrieval=StubRetrieval()),
        reasoning,
    )


# -- what reaches the prompt ------------------------------------------------


def test_the_system_prompt_carries_the_grounding_block() -> None:
    agent, reasoning = agent_with(ask("fever", pain="severe"))
    agent.run_turn([Message(role="user", content="bad pain")], observed={"pain": "severe"})

    prompt = reasoning.prompts[0]
    assert "ALREADY ANSWERED, do not ask about any of these again: pain=severe" in prompt
    assert "Outstanding: fever equals yes" in prompt
    assert "QUESTIONS YOU MAY ASK NEXT" in prompt


def test_the_retired_blocks_no_longer_reach_the_prompt() -> None:
    """``render_feature_vocabulary``'s 39 bare ids and ``render_red_flags``'s
    clause-stripped list are what this replaced; both still exist for
    ``bootstrap_dataset`` and for reproducing the comparison, but neither
    belongs on the serving path any more."""
    agent, reasoning = agent_with(ask("fever", pain="severe"))
    agent.run_turn([Message(role="user", content="bad pain")], observed={"pain": "severe"})

    prompt = reasoning.prompts[0]
    assert "Closed vocabulary for next_feature_id" not in prompt
    assert "Known warning signs — check every one of these" not in prompt


def test_retrieved_passages_are_not_rendered_twice() -> None:
    """The agent leaves passage rendering to the reasoning client, which also
    needs them for retry feedback. Rendering them here as well would put the
    same text in the prompt twice."""
    agent, reasoning = agent_with(ask("fever", pain="severe"))
    agent.run_turn([Message(role="user", content="bad pain")], observed={"pain": "severe"})
    assert PASSAGE.text not in reasoning.prompts[0]


def test_an_empty_case_vector_still_produces_a_usable_block() -> None:
    agent, reasoning = agent_with(ask("pain"))
    agent.run_turn([Message(role="user", content="hello")])
    assert "nothing yet" in reasoning.prompts[0]


# -- what carries between turns ---------------------------------------------


def test_observed_accumulates_across_turns() -> None:
    agent, reasoning = agent_with(
        ask("pain"),
        ask("fever", pain="severe"),
        ask("bleeding", fever="yes"),
        conclude(),
    )
    transcript = agent.run_consultation("my tummy hurts", lambda decision: "answering")

    assert transcript.turns_taken == 4
    # Turn 4's prompt knows both answers, though each arrived on its own turn.
    assert "fever=yes" in reasoning.prompts[3]
    assert "pain=severe" in reasoning.prompts[3]


def test_the_case_vector_lags_the_newest_message_by_one_turn() -> None:
    """A property of one model call per turn, stated rather than hidden.

    A decision reports what it understood from the message it just read, so
    turn N's grounding block is built from turns 1..N-1. The block cannot
    contain an answer nobody has extracted yet — extracting it is what the
    model is doing on this very call.
    """
    agent, reasoning = agent_with(
        ask("pain"),
        ask("fever", pain="severe"),
        conclude(fever="yes"),
    )
    agent.run_consultation("my tummy hurts", lambda decision: "answering")

    assert "pain=severe" in reasoning.prompts[2]
    assert "fever=yes" not in reasoning.prompts[2]


def test_a_rule_stays_live_on_the_turn_its_answer_arrives() -> None:
    """The regression that matters most here.

    ``fever`` is asked on turn 2, so from turn 3 it is *pending* — asked, not
    yet answered. Turn 3 is the turn that reads her reply. If pending counted
    as answered, the block would have stopped flagging
    ``severe_pain_with_fever`` as one answer away at precisely the moment the
    completing answer arrived, and an EMERGENCY escalation would depend on the
    model noticing unaided.
    """
    agent, reasoning = agent_with(
        ask("pain"),
        ask("fever", pain="severe"),
        conclude(fever="yes"),
    )
    agent.run_consultation("my tummy hurts", lambda decision: "answering")

    third = reasoning.prompts[2]
    assert "WARNING SIGNS ONE ANSWER AWAY" in third
    assert "Outstanding: fever equals yes" in third
    # Still not re-offered as a question — she was already asked.
    assert "next_feature_id=fever" not in third


def test_a_completed_rule_is_reported_as_met_once_its_answer_is_in() -> None:
    agent, reasoning = agent_with(
        ask("pain"),
        ask("fever", pain="severe"),
        ask("bleeding", fever="yes"),
        conclude(),
    )
    agent.run_consultation("my tummy hurts", lambda decision: "answering")

    assert "A WARNING SIGN IS ALREADY MET: red_flag_id=severe_pain_with_fever" in (
        reasoning.prompts[3]
    )


def test_a_later_reading_overwrites_an_earlier_one() -> None:
    """She may correct herself, and the newer answer is the one that counts."""
    agent, reasoning = agent_with(
        ask("fever", pain="mild"),
        ask("bleeding", pain="severe"),
        conclude(),
    )
    agent.run_consultation("some pain", lambda decision: "actually it is severe")

    assert "pain=severe" in reasoning.prompts[2]
    assert "pain=mild" not in reasoning.prompts[2]


def test_a_feature_asked_but_not_answered_is_not_asked_again() -> None:
    """The question went out, so it must not be offered again — but the rule
    it would complete stays live until a value actually comes back."""
    agent, reasoning = agent_with(
        ask("fever", pain="severe"),
        ask("bleeding"),
        conclude(),
    )
    agent.run_consultation("bad pain", lambda decision: "I do not know")

    second = reasoning.prompts[1]
    assert "next_feature_id=fever" not in second
    assert "Outstanding: fever equals yes" in second


def test_an_answer_of_unknown_does_kill_the_rule() -> None:
    """"Asked, and she said she does not know" is an answer. It is recorded in
    the case vector, cannot satisfy the clause, and ends the rule — which is
    what stops the screen looping."""
    agent, reasoning = agent_with(
        ask("fever", pain="severe"),
        ask("bleeding", fever="unknown"),
        conclude(),
    )
    agent.run_consultation("bad pain", lambda decision: "I do not know")

    third = reasoning.prompts[2]
    assert "Outstanding: fever equals yes" not in third
    assert "WARNING SIGNS ONE ANSWER AWAY" not in third


# -- the abstention gate ----------------------------------------------------


def conclude_decision(action: str = "ROUTINE_APPOINTMENT", **observed: str) -> TriageDecision:
    return TriageDecision(
        type=DecisionType.CONCLUDE,
        action_code=action,
        red_flag_id="severe_pain_with_fever",
        rationale="This is the urgency.",
        observed=observed,
    )


def gated_agent(*decisions: TriageDecision) -> tuple[TriageAgent, CapturingReasoning]:
    reasoning = CapturingReasoning(decisions)
    agent = TriageAgent(
        base=build(),
        reasoning=reasoning,
        retrieval=StubRetrieval(),
        min_answers=3,
    )
    return agent, reasoning


def test_a_fired_rule_is_never_sent_back_for_being_thin() -> None:
    """The safety bug this test exists to prevent.

    A woman with no stored date of birth, reporting severe pain and fever, has
    two answers recorded when the rule fires. The first version of the gate
    counted those two answers, decided the consultation was too thin, and sent
    an EMERGENCY-class conclusion back to ask a third question — delaying an
    escalation for the sake of a count, which is the exact failure this
    project exists to prevent.
    """
    agent, reasoning = gated_agent(conclude_decision("EMERGENCY"))
    turn = agent.run_turn(
        [Message(role="user", content="severe pain and a fever")],
        observed={"pain": "severe", "fever": "yes"},
        asked=["pain", "fever"],
    )
    assert turn.decision.type is DecisionType.CONCLUDE
    assert len(reasoning.prompts) == 1  # never re-prompted


def test_a_conclusion_is_sent_back_when_a_worse_warning_sign_is_one_answer_away() -> None:
    """The escalation screen: this challenge asks her to escalate further,
    never to wait."""
    agent, reasoning = gated_agent(
        conclude_decision("ROUTINE_APPOINTMENT"),
        ask("fever", pain="severe"),
    )
    turn = agent.run_turn(
        [Message(role="user", content="bad pain")],
        observed={"pain": "severe"},
        asked=["pain"],
    )
    assert turn.decision.type is DecisionType.ASK
    assert len(reasoning.prompts) == 2
    assert "CONCLUDED TOO EARLY" in reasoning.prompts[1]
    assert "fever" in reasoning.prompts[1]


def test_a_conclusion_from_almost_nothing_is_sent_back() -> None:
    agent, reasoning = gated_agent(
        conclude_decision("ROUTINE_APPOINTMENT"),
        ask("fever", bleeding="heavy"),
    )
    turn = agent.run_turn(
        [Message(role="user", content="heavy bleeding")],
        observed={"bleeding": "heavy"},
        asked=["bleeding"],
    )
    assert turn.decision.type is DecisionType.ASK
    assert len(reasoning.prompts) == 2


def test_a_conclusion_with_enough_answers_stands() -> None:
    agent, reasoning = gated_agent(conclude_decision("ROUTINE_APPOINTMENT"))
    turn = agent.run_turn(
        [Message(role="user", content="…")],
        observed={"bleeding": "heavy", "private_question": "no", "fever": "no"},
        asked=["bleeding", "private_question", "fever"],
    )
    assert turn.decision.type is DecisionType.CONCLUDE
    assert len(reasoning.prompts) == 1


def test_the_gate_gives_way_rather_than_looping() -> None:
    """If the model concludes again after being told, that conclusion stands."""
    agent, reasoning = gated_agent(
        conclude_decision("ROUTINE_APPOINTMENT"),
        conclude_decision("ROUTINE_APPOINTMENT"),
    )
    turn = agent.run_turn(
        [Message(role="user", content="heavy bleeding")],
        observed={"bleeding": "heavy"},
        asked=["bleeding"],
    )
    assert turn.decision.type is DecisionType.CONCLUDE
    assert len(reasoning.prompts) == 2  # challenged once, not twice


def test_the_gate_is_off_unless_the_deployment_turns_it_on() -> None:
    agent, reasoning = agent_with(conclude_decision("ROUTINE_APPOINTMENT"))
    turn = agent.run_turn(
        [Message(role="user", content="heavy bleeding")],
        observed={"bleeding": "heavy"},
        asked=["bleeding"],
    )
    assert turn.decision.type is DecisionType.CONCLUDE
    assert len(reasoning.prompts) == 1


# ---------------------------------------------------------------------------
# Attribution: which model actually answered
# ---------------------------------------------------------------------------


def test_a_turn_served_without_incident_names_one_backend() -> None:
    agent = TriageAgent(
        base=build(),
        reasoning=ScriptedReasoningClient(
            [ask("fever", bleeding="heavy")], name="vllm:herhealth"
        ),
        retrieval=StubRetrieval(),
        min_answers=3,
    )
    turn = agent.run_turn(
        [Message(role="user", content="heavy bleeding")],
        observed={"bleeding": "heavy"},
    )
    assert turn.served_by == "vllm:herhealth"
    assert len(turn.attempts) == 1
