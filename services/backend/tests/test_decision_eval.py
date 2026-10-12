"""The decision evaluation's arithmetic and its multi-turn runner, with a
scripted decision model. No endpoint is involved."""

from __future__ import annotations

from pathlib import Path

import pytest
from herhealth_contracts.decision import DecisionType, TriageDecision
from herhealth_contracts.knowledge import ActionCode, KnowledgeBase
from herhealth_contracts.loading import load_knowledge_base
from herhealth_contracts.retrieval import PassageType, RetrievedPassage

from herhealth_backend.evaluation.decision_eval import (
    Question,
    Script,
    TurnRecord,
    load_questions,
    load_scripts,
    run_first_turns,
    run_script,
    summarise_first_turns,
)
from herhealth_backend.triage.agent import (
    AttemptOutcome,
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


@pytest.fixture(scope="module")
def base() -> KnowledgeBase:
    return load_knowledge_base(REPO / "knowledge")


def ask(feature_id: str) -> TriageDecision:
    return TriageDecision(
        type=DecisionType.ASK,
        rationale="One more detail would help.",
        next_feature_id=feature_id,
        question_text="A placeholder question?",
        citations=(PASSAGE.id,),
    )


def conclude() -> TriageDecision:
    return TriageDecision(
        type=DecisionType.CONCLUDE,
        rationale="A placeholder reason.",
        action_code=ActionCode.ROUTINE_APPOINTMENT,
        citations=(PASSAGE.id,),
    )


class Reasoning:
    name = "scripted"

    def __init__(self, *decisions: TriageDecision | Exception) -> None:
        self.decisions = list(decisions)
        self.user_messages: list[str] = []

    def decide(self, *, system_prompt, history, context):  # type: ignore[no-untyped-def]
        self.user_messages.append(history[-1].content)
        decision = self.decisions.pop(0)
        if isinstance(decision, Exception):
            raise decision
        return ReasoningResult(
            decision=decision,
            attempts=(ReasoningAttempt(client=self.name, outcome=AttemptOutcome.OK),),
        )


class Retrieval:
    def search(self, query: str, *, k: int = 8) -> list[RetrievedPassage]:
        return [PASSAGE]


def _agent(base: KnowledgeBase, reasoning: Reasoning) -> TriageAgent:
    return TriageAgent(base=base, reasoning=reasoning, retrieval=Retrieval())


def _question(n: int, own: bool) -> Question:
    return Question(id=n, style="layperson", question=f"question {n}", describes_own_symptoms=own)


def test_the_committed_inputs_load() -> None:
    questions = load_questions(REPO / "services/data/eval/decision_questions.jsonl")
    scripts = load_scripts(REPO / "services/data/eval/decision_scripts.jsonl")
    assert len(questions) == 30
    assert sum(q.describes_own_symptoms for q in questions) == 12
    assert len(scripts) == 10
    assert all(script.opening and script.answers for script in scripts)


def test_first_turns_record_valid_and_invalid_replies(base: KnowledgeBase) -> None:
    reasoning = Reasoning(ask("cycle_length"), ValueError("no JSON object"), conclude())
    records = run_first_turns(
        _agent(base, reasoning), [_question(1, True), _question(2, True), _question(3, False)]
    )
    assert [r.ok for r in records] == [True, False, True]
    assert [r.type for r in records] == ["ask", None, "conclude"]
    assert "no JSON object" in (records[1].error or "")


def test_summary_arithmetic() -> None:
    def record(n: int, own: bool, kind: str | None, seconds: float) -> TurnRecord:
        return TurnRecord(
            question=_question(n, own),
            ok=kind is not None,
            type=kind,
            action=None,
            seconds=seconds,
            error=None if kind else "boom",
            attempts=(),
        )

    summary = summarise_first_turns(
        [
            record(1, True, "ask", 10),
            record(2, True, "inform", 20),
            record(3, True, None, 30),
            record(4, False, "inform", 40),
        ]
    )
    assert summary["questions"] == 4
    assert summary["valid"] == 3
    assert summary["by_type"] == {"ask": 1, "inform": 2}
    assert summary["median_seconds"] == 25
    own = summary["describing_own_symptoms"]
    assert own == {"questions": 3, "valid": 2, "asked": 1, "concluded": 0, "informed": 1}


def test_a_script_supplies_her_replies_and_reaches_a_conclusion(base: KnowledgeBase) -> None:
    reasoning = Reasoning(ask("cycle_length"), ask("fever"), conclude())
    script = Script(
        id="s1",
        opening="my periods are all over the place",
        answers={"cycle_length": "About every 40 days."},
    )
    result = run_script(_agent(base, reasoning), script)
    assert result.concluded is True
    assert result.turns == 3
    assert result.action == "ROUTINE_APPOINTMENT"
    assert result.asked == ("cycle_length", "fever")
    assert reasoning.user_messages == [
        "my periods are all over the place",
        "About every 40 days.",
        "No.",
    ]


def test_a_script_that_runs_out_of_turns_is_unfinished(base: KnowledgeBase) -> None:
    reasoning = Reasoning(*(ask("fever") for _ in range(3)))
    result = run_script(
        _agent(base, reasoning), Script(id="s2", opening="x", answers={}), max_turns=3
    )
    assert result.concluded is False
    assert result.turns == 3
    assert result.error is None


def test_a_script_whose_reply_is_invalid_records_the_error(base: KnowledgeBase) -> None:
    result = run_script(
        _agent(base, Reasoning(ValueError("bad reply"))), Script(id="s3", opening="x", answers={})
    )
    assert result.concluded is False
    assert "bad reply" in (result.error or "")
