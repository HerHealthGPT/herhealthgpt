"""Detecting the language she writes in, and replying in it."""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage

from herhealth_backend.triage.agent import Message
from herhealth_backend.triage.comparison import PlainChatResponder
from herhealth_backend.triage.language import (
    ARABIC,
    FRENCH,
    detect_language,
    language_instruction,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("دورتي الشهرية غير منتظمة", ARABIC),
        ("عندي ألم شديد من 3 أيام", ARABIC),
        ("ما هو PCOS؟", ARABIC),
        ("Mes règles sont irrégulières depuis trois mois", FRENCH),
        ("Qu'est-ce que le SOPK ?", FRENCH),
        ("oui", FRENCH),
        ("My periods have been irregular lately", None),
        ("What is PCOS?", None),
        ("I pour water on the table", None),
        ("no", None),
    ],
)
def test_the_language_of_one_message(text: str, expected: str | None) -> None:
    assert detect_language([text]) == expected


def test_a_reply_with_no_letters_keeps_the_language_of_the_conversation() -> None:
    assert detect_language(["دورتي الشهرية غير منتظمة", "29"]) == ARABIC


def test_the_newest_message_with_words_decides() -> None:
    assert (
        detect_language(["Mes règles sont irrégulières", "Actually I'll write in English"]) is None
    )


def test_no_instruction_is_added_for_english() -> None:
    assert language_instruction(None) == ""
    assert "Arabic" in language_instruction(ARABIC)


class _Chat:
    def __init__(self) -> None:
        self.seen: list[object] = []

    def invoke(self, messages: list[object]) -> AIMessage:
        self.seen = messages
        return AIMessage(content="نعم")


def test_a_comparison_model_is_told_the_language() -> None:
    chat = _Chat()

    PlainChatResponder(chat, name="m").reply([Message("user", "ما هي أعراض تكيس المبايض؟")])

    assert "answer in Arabic" in chat.seen[0].content  # type: ignore[attr-defined]


# --- The interface language as a fallback, inside a real turn -------------

from pathlib import Path  # noqa: E402

from herhealth_contracts.decision import DecisionType, TriageDecision  # noqa: E402
from herhealth_contracts.loading import load_knowledge_base  # noqa: E402
from herhealth_contracts.retrieval import PassageType, RetrievedPassage  # noqa: E402

from herhealth_backend.triage.agent import (  # noqa: E402
    AttemptOutcome,
    ReasoningAttempt,
    ReasoningResult,
    TriageAgent,
)

_PASSAGE = RetrievedPassage(
    id="0123456789abcdef",
    passage_type=PassageType.SOURCE_PASSAGE,
    source_id="womenshealth",
    text="A placeholder passage.",
    citation="womenshealth/page",
    score=0.5,
)


class _Reasoning:
    name = "decision-model"

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def decide(self, *, system_prompt, history, context):  # type: ignore[no-untyped-def]
        self.prompts.append(system_prompt)
        decision = TriageDecision(
            type=DecisionType.ASK,
            rationale="One more detail would help.",
            next_feature_id="cycle_length",
            question_text="How many days are there between your periods?",
        )
        return ReasoningResult(
            decision=decision,
            attempts=(ReasoningAttempt(client=self.name, outcome=AttemptOutcome.OK),),
        )


class _Retrieval:
    def search(self, query: str, *, k: int = 8) -> list[RetrievedPassage]:
        return [_PASSAGE]


def _prompt_for(message: str, fallback: str | None) -> str:
    reasoning = _Reasoning()
    agent = TriageAgent(
        base=load_knowledge_base(Path(__file__).resolve().parents[3] / "knowledge"),
        reasoning=reasoning,
        retrieval=_Retrieval(),
    )
    agent.run_turn([Message(role="user", content=message)], fallback_language=fallback)
    return reasoning.prompts[0]


def test_her_own_words_decide_over_the_interface_language() -> None:
    assert "She is writing in Arabic" not in _prompt_for("My periods are irregular", "Arabic")


def test_the_interface_language_is_used_when_her_message_has_no_words() -> None:
    assert "She is writing in Arabic" in _prompt_for("29", "Arabic")


def test_no_language_line_for_english_with_no_fallback() -> None:
    assert "LANGUAGE." not in _prompt_for("My periods are irregular", None)
