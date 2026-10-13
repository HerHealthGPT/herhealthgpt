"""The comparison modes: one instruction, the conversation, nothing else."""

from __future__ import annotations

import httpx
import openai
import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from herhealth_backend.triage.agent import Message
from herhealth_backend.triage.chain import ReasoningUnavailable
from herhealth_backend.triage.comparison import (
    COMPARISON_INSTRUCTION,
    MODEL_A,
    MODEL_B,
    MODEL_C,
    MODEL_LABELS,
    PlainChatResponder,
)


class _Chat:
    def __init__(self, reply: object) -> None:
        self.reply = reply
        self.seen: list[object] = []

    def invoke(self, messages: list[object]) -> object:
        self.seen = messages
        if isinstance(self.reply, Exception):
            raise self.reply
        return AIMessage(content=self.reply)


def test_the_model_sees_the_instruction_and_the_conversation_only() -> None:
    chat = _Chat("PCOS is a hormonal condition.")
    history = [
        Message(role="user", content="What is PCOS?"),
        Message(role="assistant", content="A hormonal condition."),
        Message(role="user", content="Is it common?"),
    ]

    answer = PlainChatResponder(chat, name="herhealth").reply(history)

    assert answer == "PCOS is a hormonal condition."
    assert [type(message) for message in chat.seen] == [
        SystemMessage,
        HumanMessage,
        AIMessage,
        HumanMessage,
    ]
    assert chat.seen[0].content == COMPARISON_INSTRUCTION  # type: ignore[attr-defined]


def test_a_thinking_block_is_not_shown_to_her() -> None:
    chat = _Chat("<think>she asked about periods</think>\nPeriods vary.")

    assert PlainChatResponder(chat, name="m").reply([Message("user", "hi")]) == "Periods vary."


@pytest.mark.parametrize("reply", ["", "   ", "<think>nothing else</think>"])
def test_an_empty_reply_is_a_failed_turn(reply: str) -> None:
    with pytest.raises(ReasoningUnavailable):
        PlainChatResponder(_Chat(reply), name="m").reply([Message("user", "hi")])


def test_a_timeout_or_refused_connection_is_an_http_error() -> None:
    request = httpx.Request("POST", "http://example.invalid/v1/chat/completions")
    for failure in (
        openai.APITimeoutError(request=request),
        openai.APIConnectionError(request=request),
    ):
        with pytest.raises(httpx.HTTPError):
            PlainChatResponder(_Chat(failure), name="m").reply([Message("user", "hi")])


def test_the_labels_say_nothing_about_what_each_mode_is() -> None:
    assert MODEL_LABELS == {MODEL_A: "Model A", MODEL_B: "Model B", MODEL_C: "Model C"}
