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
