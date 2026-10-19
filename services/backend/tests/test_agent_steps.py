"""The three additions to a turn: the extract step, the inform gate and the
answer step. A scripted decision model and stub seams; the knowledge base is
the real tracked one."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pytest
from herhealth_contracts.decision import DecisionType, TriageDecision
from herhealth_contracts.knowledge import KnowledgeBase
from herhealth_contracts.loading import load_knowledge_base
from herhealth_contracts.retrieval import PassageType, RetrievedPassage

from herhealth_backend.triage.agent import (
    AttemptOutcome,
    Message,
    ReasoningAttempt,
    ReasoningResult,
    TriageAgent,
)

REPO = Path(__file__).resolve().parents[3]
PASSAGE = RetrievedPassage(
    id="0123456789abcdef",
    passage_type=PassageType.SOURCE_PASSAGE,
    source_id="womenshealth",
    text="A placeholder passage.",
    citation="womenshealth/page",
    score=0.5,
)
OTHER = PASSAGE.model_copy(update={"id": "fedcba9876543210", "text": "Another placeholder."})
BASE_ANSWER = (
    "An explanation.\n\nWhen to get medical help:\n- Get emergency care now if it is sudden."
)


@pytest.fixture(scope="module")
def base() -> KnowledgeBase:
    return load_knowledge_base(REPO / "knowledge")


def inform() -> TriageDecision:
    return TriageDecision(
        type=DecisionType.INFORM,
        rationale="A general question about the subject.",
        answer_text=BASE_ANSWER,
        citations=(PASSAGE.id,),
    )


def ask(feature_id: str = "cycle_length") -> TriageDecision:
    return TriageDecision(
        type=DecisionType.ASK,
        rationale="One more detail would help.",
        next_feature_id=feature_id,
        question_text="How many days are there between your periods?",
        citations=(PASSAGE.id,),
    )


class Reasoning:
    name = "decision-model"

    def __init__(self, *decisions: TriageDecision) -> None:
        self.decisions = list(decisions)
        self.prompts: list[str] = []

    def decide(self, *, system_prompt, history, context):  # type: ignore[no-untyped-def]
        self.prompts.append(system_prompt)
        return ReasoningResult(
            decision=self.decisions.pop(0),
            attempts=(ReasoningAttempt(client=self.name, outcome=AttemptOutcome.OK),),
        )


class Retrieval:
    def search(self, query: str, *, k: int = 8) -> list[RetrievedPassage]:
        return [PASSAGE, OTHER]


class Extractor:
    def __init__(self, found: dict[str, str]) -> None:
        self.found = found
        self.pending: list[str | None] = []

    def extract(self, history: Sequence[Message], *, pending_feature: str | None) -> dict[str, str]:
        self.pending.append(pending_feature)
        return dict(self.found)


class Writer:
    name = "answer-model"

    def __init__(self, text: str | None) -> None:
        self.text = text
        self.calls: list[tuple[str, list[str], str]] = []

    def write(
        self, question: str, passages: Sequence[RetrievedPassage], base_answer: str
    ) -> str | None:
        self.calls.append((question, [p.id for p in passages], base_answer))
        return self.text


def turn(agent: TriageAgent, message: str = "a placeholder message", **kwargs):  # type: ignore[no-untyped-def]
    return agent.run_turn([Message(role="user", content=message)], **kwargs)


# --- extract ------------------------------------------------------------------


def test_the_agent_runs_without_an_extractor(base: KnowledgeBase) -> None:
    agent = TriageAgent(base=base, reasoning=Reasoning(ask()), retrieval=Retrieval())
    assert turn(agent).decision.type is DecisionType.ASK


def test_extracted_values_reach_the_turn_context(base: KnowledgeBase) -> None:
    reasoning = Reasoning(ask())
    agent = TriageAgent(
        base=base,
        reasoning=reasoning,
        retrieval=Retrieval(),
        extractor=Extractor({"cycle_regularity": "irregular"}),
    )
    turn(agent)
    assert "cycle_regularity" in reasoning.prompts[0]
    assert "irregular" in reasoning.prompts[0]


def test_extracted_values_are_returned_on_the_decision(base: KnowledgeBase) -> None:
    agent = TriageAgent(
        base=base,
        reasoning=Reasoning(ask()),
        retrieval=Retrieval(),
        extractor=Extractor({"cycle_regularity": "irregular"}),
    )
    assert turn(agent).decision.observed == {"cycle_regularity": "irregular"}


def test_the_extractor_is_told_which_question_is_pending(base: KnowledgeBase) -> None:
    extractor = Extractor({})
    agent = TriageAgent(
        base=base, reasoning=Reasoning(ask()), retrieval=Retrieval(), extractor=extractor
    )
    turn(agent, asked=["cycle_length"], observed={})
    assert extractor.pending == ["cycle_length"]


# --- the inform gate ----------------------------------------------------------


def _gated(base: KnowledgeBase, reasoning: Reasoning, found: dict[str, str]) -> TriageAgent:
    return TriageAgent(
        base=base,
        reasoning=reasoning,
        retrieval=Retrieval(),
        extractor=Extractor(found),
        refuse_inform_with_symptoms=True,
    )


def test_inform_is_refused_when_she_described_a_symptom(base: KnowledgeBase) -> None:
    reasoning = Reasoning(inform(), ask())
    result = turn(_gated(base, reasoning, {"cycle_regularity": "irregular"}))
    assert result.decision.type is DecisionType.ASK
    assert len(reasoning.prompts) == 2
    assert "REJECTED" in reasoning.prompts[1]
    assert len(result.attempts) == 2


def test_inform_is_accepted_when_nothing_is_recorded(base: KnowledgeBase) -> None:
    reasoning = Reasoning(inform())
    assert turn(_gated(base, reasoning, {})).decision.type is DecisionType.INFORM
    assert len(reasoning.prompts) == 1


def test_a_profile_age_band_alone_does_not_refuse(base: KnowledgeBase) -> None:
    reasoning = Reasoning(inform())
    result = turn(_gated(base, reasoning, {}), observed={"age_band": "30_to_39"})
    assert result.decision.type is DecisionType.INFORM


def test_a_second_inform_stands(base: KnowledgeBase) -> None:
    reasoning = Reasoning(inform(), inform())
    result = turn(_gated(base, reasoning, {"cycle_regularity": "irregular"}))
    assert result.decision.type is DecisionType.INFORM
    assert len(reasoning.prompts) == 2


def test_the_gate_is_off_by_default(base: KnowledgeBase) -> None:
    reasoning = Reasoning(inform())
    agent = TriageAgent(
        base=base,
        reasoning=reasoning,
        retrieval=Retrieval(),
        extractor=Extractor({"cycle_regularity": "irregular"}),
    )
    assert turn(agent).decision.type is DecisionType.INFORM
    assert len(reasoning.prompts) == 1


# --- the answer step ----------------------------------------------------------


def test_the_writer_replaces_the_answer_of_an_inform(base: KnowledgeBase) -> None:
    writer = Writer("The adapter's wording.")
    agent = TriageAgent(
        base=base, reasoning=Reasoning(inform()), retrieval=Retrieval(), answer_writer=writer
    )
    result = turn(agent, "what is it?")
    assert result.decision.answer_text == "The adapter's wording."
    assert writer.calls == [("what is it?", [PASSAGE.id], BASE_ANSWER)]  # only the cited passage
    assert [(a.client, a.outcome) for a in result.attempts] == [
        ("decision-model", AttemptOutcome.OK),
        ("answer-model", AttemptOutcome.OK),
    ]


def test_an_unusable_answer_keeps_the_base_answer(base: KnowledgeBase) -> None:
    agent = TriageAgent(
        base=base, reasoning=Reasoning(inform()), retrieval=Retrieval(), answer_writer=Writer(None)
    )
    result = turn(agent)
    assert result.decision.answer_text == BASE_ANSWER
    assert result.attempts[-1].outcome is AttemptOutcome.REJECTED
    assert result.served_by == "decision-model"


def test_the_writer_runs_only_for_inform(base: KnowledgeBase) -> None:
    writer = Writer("unused")
    agent = TriageAgent(
        base=base, reasoning=Reasoning(ask()), retrieval=Retrieval(), answer_writer=writer
    )
    turn(agent)
    assert writer.calls == []


# --- found in review ----------------------------------------------------------


def conclude_urgent() -> TriageDecision:
    from herhealth_contracts.knowledge import ActionCode

    return TriageDecision(
        type=DecisionType.CONCLUDE,
        rationale="This needs to be seen today.",
        action_code=ActionCode.URGENT_SAME_DAY,
        citations=(PASSAGE.id,),
    )


def test_a_conclusion_reached_through_the_inform_gate_is_still_challenged(
    base: KnowledgeBase,
) -> None:
    # inform -> (refused) -> conclude on one recorded answer must meet the
    # early-conclusion gate, exactly as a direct conclusion would.
    reasoning = Reasoning(inform(), conclude_urgent(), ask())
    agent = TriageAgent(
        base=base,
        reasoning=reasoning,
        retrieval=Retrieval(),
        extractor=Extractor({"cycle_regularity": "irregular"}),
        refuse_inform_with_symptoms=True,
        min_answers=3,
    )
    result = turn(agent)
    assert len(reasoning.prompts) == 3
    assert "CONCLUDED TOO EARLY" in reasoning.prompts[2]
    assert result.decision.type is DecisionType.ASK


class ExplodingWriter:
    name = "answer-model"

    def write(self, question, passages, base_answer):  # type: ignore[no-untyped-def]
        raise RuntimeError("an error nobody anticipated")


def test_an_unexpected_writer_error_keeps_the_base_answer(base: KnowledgeBase) -> None:
    agent = TriageAgent(
        base=base,
        reasoning=Reasoning(inform()),
        retrieval=Retrieval(),
        answer_writer=ExplodingWriter(),
    )
    result = turn(agent)
    assert result.decision.answer_text == BASE_ANSWER
    assert result.attempts[-1].outcome is AttemptOutcome.REJECTED


# --- repeated questions (2026-10-12) -------------------------------------------


def test_the_pending_question_is_the_last_one_asked_even_if_already_recorded(
    base: KnowledgeBase,
) -> None:
    # The model may re-ask something a wrong extraction recorded earlier. Her
    # reply must still be read as the answer to it, or the question loops.
    extractor = Extractor({})
    agent = TriageAgent(
        base=base, reasoning=Reasoning(ask()), retrieval=Retrieval(), extractor=extractor
    )
    turn(agent, asked=["cycle_regularity"], observed={"cycle_regularity": "irregular"})
    assert extractor.pending == ["cycle_regularity"]


def _repeat_guarded(base: KnowledgeBase, reasoning: Reasoning) -> TriageAgent:
    return TriageAgent(
        base=base, reasoning=reasoning, retrieval=Retrieval(), refuse_repeated_question=True
    )


def test_asking_the_question_she_just_answered_is_refused_once(base: KnowledgeBase) -> None:
    reasoning = Reasoning(ask("cycle_length"), ask("fever"))
    result = turn(
        _repeat_guarded(base, reasoning),
        asked=["cycle_length"],
        observed={"cycle_length": "over_35_days"},
    )
    assert result.decision.next_feature_id == "fever"
    assert len(reasoning.prompts) == 2
    assert "cycle_length" in reasoning.prompts[1] and "ALREADY ANSWERED" in reasoning.prompts[1]


def test_a_second_repeat_is_refused_naming_the_question_to_ask(base: KnowledgeBase) -> None:
    reasoning = Reasoning(ask("cycle_length"), ask("cycle_length"), ask("period_duration"))
    result = turn(
        _repeat_guarded(base, reasoning),
        asked=["cycle_length"],
        observed={"cycle_length": "over_35_days"},
    )
    assert result.decision.next_feature_id == "period_duration"
    assert len(reasoning.prompts) == 3
    assert "YOU REPEATED THE QUESTION AGAIN" in reasoning.prompts[-1]


def test_a_third_repeat_is_replaced_by_the_menu_question_in_code(base: KnowledgeBase) -> None:
    reasoning = Reasoning(ask("cycle_length"), ask("cycle_length"), ask("cycle_length"))
    result = turn(
        _repeat_guarded(base, reasoning),
        asked=["cycle_length"],
        observed={"cycle_length": "over_35_days"},
    )
    assert result.decision.type is DecisionType.ASK
    assert result.decision.next_feature_id != "cycle_length"
    assert result.decision.question_text
    assert result.attempts[-1].client == "repeat-gate"


def test_an_earlier_answered_question_counts_as_a_repeat(base: KnowledgeBase) -> None:
    reasoning = Reasoning(ask("cycle_length"), ask("period_duration"))
    result = turn(
        _repeat_guarded(base, reasoning),
        asked=["cycle_length", "fever"],
        observed={"cycle_length": "over_35_days", "fever": "no"},
    )
    assert result.decision.next_feature_id == "period_duration"


def test_the_last_question_unanswered_is_not_asked_straight_back(base: KnowledgeBase) -> None:
    reasoning = Reasoning(ask("cycle_length"), ask("period_duration"))
    result = turn(_repeat_guarded(base, reasoning), asked=["cycle_length"], observed={})
    assert result.decision.next_feature_id == "period_duration"
    assert "ON THE LAST TURN" in reasoning.prompts[1]


def test_an_older_unanswered_question_may_be_asked_again(base: KnowledgeBase) -> None:
    reasoning = Reasoning(ask("cycle_length"))
    result = turn(
        _repeat_guarded(base, reasoning), asked=["cycle_length", "fever"], observed={"fever": "no"}
    )
    assert result.decision.next_feature_id == "cycle_length"
    assert len(reasoning.prompts) == 1


# --- The red-flag gate -------------------------------------------------------


def _conclude(action: str, red_flag: str | None = None) -> TriageDecision:
    from herhealth_contracts.knowledge import ActionCode

    return TriageDecision(
        type=DecisionType.CONCLUDE,
        rationale="Here is how soon to be seen.",
        action_code=ActionCode(action),
        red_flag_id=red_flag,
        citations=() if red_flag else (PASSAGE.id,),
    )


FAINT = {"pelvic_pain_severity": "mild", "feeling_faint": "yes"}


def test_a_fired_rule_sends_a_question_back_and_takes_the_escalation(
    base: KnowledgeBase,
) -> None:
    reasoning = Reasoning(ask(), _conclude("EMERGENCY", "pelvic_pain_with_faintness"))
    agent = TriageAgent(
        base=base, reasoning=reasoning, retrieval=Retrieval(), enforce_red_flags=True
    )

    result = turn(agent, observed=dict(FAINT))

    assert result.decision.action_code.value == "EMERGENCY"  # type: ignore[union-attr]
    assert "pelvic_pain_with_faintness" in reasoning.prompts[-1]


def test_code_concludes_when_the_model_still_does_not_escalate(base: KnowledgeBase) -> None:
    agent = TriageAgent(
        base=base, reasoning=Reasoning(ask(), ask()), retrieval=Retrieval(), enforce_red_flags=True
    )

    result = turn(agent, observed=dict(FAINT))

    assert result.decision.type is DecisionType.CONCLUDE
    assert result.decision.action_code.value == "EMERGENCY"  # type: ignore[union-attr]
    assert result.decision.red_flag_id == "pelvic_pain_with_faintness"
    assert result.attempts[-1].client == "red-flag-gate"


def test_no_fired_rule_leaves_the_reply_alone(base: KnowledgeBase) -> None:
    agent = TriageAgent(
        base=base, reasoning=Reasoning(ask()), retrieval=Retrieval(), enforce_red_flags=True
    )

    assert turn(agent).decision.type is DecisionType.ASK


def test_the_red_flag_gate_is_off_by_default(base: KnowledgeBase) -> None:
    agent = TriageAgent(base=base, reasoning=Reasoning(ask()), retrieval=Retrieval())

    assert turn(agent, observed=dict(FAINT)).decision.type is DecisionType.ASK


# --- What an informational question is about ------------------------------


class Topics:
    def __init__(self, found: tuple[str, ...]) -> None:
        self.found = found
        self.questions: list[str] = []

    def mentioned(self, question: str) -> tuple[str, ...]:
        self.questions.append(question)
        return self.found


def test_an_inform_carries_what_its_question_is_about(base: KnowledgeBase) -> None:
    topics = Topics(("pelvic_pain_severity",))
    agent = TriageAgent(
        base=base, reasoning=Reasoning(inform()), retrieval=Retrieval(), symptom_topics=topics
    )

    result = turn(agent, "What should I do if my period pain is severe?")

    assert result.mentioned == ("pelvic_pain_severity",)
    assert topics.questions == ["What should I do if my period pain is severe?"]


def test_a_question_is_not_read_for_topics(base: KnowledgeBase) -> None:
    topics = Topics(("pelvic_pain_severity",))
    agent = TriageAgent(
        base=base, reasoning=Reasoning(ask()), retrieval=Retrieval(), symptom_topics=topics
    )

    assert turn(agent).mentioned == ()
    assert topics.questions == []


def test_a_failing_topic_reader_never_fails_the_turn(base: KnowledgeBase) -> None:
    class Broken:
        def mentioned(self, question: str) -> tuple[str, ...]:
            raise RuntimeError("down")

    agent = TriageAgent(
        base=base, reasoning=Reasoning(inform()), retrieval=Retrieval(), symptom_topics=Broken()
    )

    assert turn(agent).mentioned == ()


# --- The decline gate ---------------------------------------------------------


def _decline() -> TriageDecision:
    return TriageDecision(type=DecisionType.DECLINE, rationale="This is outside what we cover.")


def test_a_decline_is_sent_back_once_and_a_question_taken(base: KnowledgeBase) -> None:
    reasoning = Reasoning(_decline(), ask())
    agent = TriageAgent(
        base=base, reasoning=reasoning, retrieval=Retrieval(), refuse_unclear_decline=True
    )

    result = turn(agent, "What does having this actually mean for me?")

    assert result.decision.type is DecisionType.ASK
    assert "DECLINED AND WAS REJECTED" in reasoning.prompts[-1]


def test_a_second_decline_stands(base: KnowledgeBase) -> None:
    agent = TriageAgent(
        base=base,
        reasoning=Reasoning(_decline(), _decline()),
        retrieval=Retrieval(),
        refuse_unclear_decline=True,
    )

    assert turn(agent, "What's the weather tomorrow?").decision.type is DecisionType.DECLINE


def test_the_decline_gate_is_off_by_default(base: KnowledgeBase) -> None:
    agent = TriageAgent(base=base, reasoning=Reasoning(_decline()), retrieval=Retrieval())

    assert turn(agent).decision.type is DecisionType.DECLINE
