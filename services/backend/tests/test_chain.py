"""The reasoning chain, offline: a scripted chat model stands in for vLLM."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

import httpx
import openai
import pytest
from herhealth_contracts.decision import DecisionType, TriageDecision
from herhealth_contracts.retrieval import PassageType, RetrievedPassage
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.runnables import RunnableLambda

from herhealth_backend.triage.agent import AttemptOutcome, Message
from herhealth_backend.triage.chain import (
    LangChainReasoningClient,
    ReasoningUnavailable,
    build_chat_model,
    extract_json_object,
)

PASSAGE = RetrievedPassage(
    id="0123456789abcdef",
    passage_type=PassageType.SOURCE_PASSAGE,
    source_id="womenshealth",
    text="A placeholder passage.",
    citation="womenshealth/page",
    score=0.5,
)
HISTORY = [Message(role="user", content="a placeholder question")]


def _decline(rationale: str = "This tool covers women's reproductive health only.") -> str:
    return json.dumps({"type": "decline", "rationale": rationale})


class Scripted:
    """Replies in order; an exception in the list is raised instead."""

    def __init__(self, *replies: Any) -> None:
        self.replies = list(replies)
        self.seen: list[Sequence[BaseMessage]] = []

    def __call__(self, messages: Sequence[BaseMessage]) -> AIMessage:
        self.seen.append(messages)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return AIMessage(content=reply)


def _client(script: Scripted, **options: Any) -> LangChainReasoningClient:
    return LangChainReasoningClient(RunnableLambda(script), name="test-model", **options)


def _decide(client: LangChainReasoningClient) -> Any:
    return client.decide(system_prompt="SYSTEM", history=HISTORY, context=[PASSAGE])


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ('{"a": 1}', '{"a": 1}'),
        ('```json\n{"a": 1}\n```', '{"a": 1}'),
        ('{"a": 1}\n\nHope that helps!', '{"a": 1}'),
        ('Here you go: {"a": {"b": "}"}} trailing', '{"a": {"b": "}"}}'),
        ('{"a": "quote \\" and brace }"}', '{"a": "quote \\" and brace }"}'),
    ],
)
def test_extract_json_object(text: str, expected: str) -> None:
    assert extract_json_object(text) == expected


def test_extract_json_object_raises_when_there_is_none() -> None:
    with pytest.raises(ValueError, match="no JSON object"):
        extract_json_object("Menopause is the time when periods stop.")


def test_a_valid_reply_is_returned_in_one_call() -> None:
    script = Scripted(_decline())
    result = _decide(_client(script))
    assert result.decision.type is DecisionType.DECLINE
    assert len(script.seen) == 1
    assert [(a.client, a.outcome) for a in result.attempts] == [("test-model", AttemptOutcome.OK)]
    system = script.seen[0][0].content
    assert system.startswith("SYSTEM")
    assert "0123456789abcdef" in system  # the retrieved passage is in the prompt
    assert script.seen[0][-1].content == "a placeholder question"


def test_a_fenced_reply_is_repaired_without_a_retry() -> None:
    script = Scripted(f"```json\n{_decline()}\n```\nLet me know if you need more.")
    assert _decide(_client(script)).decision.type is DecisionType.DECLINE
    assert len(script.seen) == 1


def test_banned_wording_is_retried_with_feedback() -> None:
    script = Scripted(_decline("You mentioned something outside this tool's scope."), _decline())
    result = _decide(_client(script))
    assert result.decision.rationale.startswith("This tool covers")
    assert len(script.seen) == 2
    assert "YOUR PREVIOUS JSON WAS REJECTED" in script.seen[1][0].content
    assert "YOUR PREVIOUS JSON WAS REJECTED" not in script.seen[0][0].content


def test_the_validator_runs_inside_the_retry_loop() -> None:
    calls: list[TriageDecision] = []

    def validator(decision: TriageDecision, context: Sequence[RetrievedPassage]) -> None:
        calls.append(decision)
        if len(calls) == 1:
            raise ValueError("unknown feature id 'made_up'")

    script = Scripted(_decline(), _decline())
    _decide(_client(script, validator=validator))
    assert len(calls) == 2
    assert "made_up" in script.seen[1][0].content


def test_two_bad_replies_raise_value_error() -> None:
    script = Scripted("plain prose, no JSON", "still prose")
    with pytest.raises(ValueError, match="no JSON object"):
        _decide(_client(script, max_attempts=2))
    assert len(script.seen) == 2


def _timeout() -> openai.APITimeoutError:
    return openai.APITimeoutError(request=httpx.Request("POST", "http://chat.test/v1"))


def test_a_timeout_is_retried() -> None:
    script = Scripted(_timeout(), _decline())
    assert _decide(_client(script)).decision.type is DecisionType.DECLINE


def test_repeated_timeouts_are_an_http_error() -> None:
    script = Scripted(_timeout(), _timeout())
    with pytest.raises(httpx.HTTPError, match="did not answer"):
        _decide(_client(script, max_attempts=2))


def test_an_unreachable_endpoint_is_an_http_error() -> None:
    down = openai.APIConnectionError(request=httpx.Request("POST", "http://chat.test/v1"))
    script = Scripted(down)
    with pytest.raises(ReasoningUnavailable):
        _decide(_client(script))
    assert len(script.seen) == 1  # an unreachable server is not retried


def test_build_chat_model_sets_temperature_tokens_and_no_retries() -> None:
    chat = build_chat_model(
        url="http://127.0.0.1:8002/",
        model="Qwen/Qwen3.5-9B",
        api_key=None,
        timeout=50.0,
        max_tokens=1200,
    )
    assert chat.temperature == 0
    assert chat.max_tokens == 1200
    assert chat.max_retries == 0
    assert chat.request_timeout == 50.0
    assert chat.model_name == "Qwen/Qwen3.5-9B"
    assert chat.extra_body == {"chat_template_kwargs": {"enable_thinking": False}}
    assert str(chat.openai_api_base).rstrip("/") == "http://127.0.0.1:8002/v1"
