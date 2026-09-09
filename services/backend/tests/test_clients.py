"""Unit tests for reasoning clients — connectivity fallback and parsing."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import httpx
import pytest
from herhealth_contracts.decision import DecisionType, TriageDecision
from herhealth_contracts.knowledge import ActionCode

from herhealth_backend.triage.agent import Message
from herhealth_backend.triage.clients import (
    FallbackReasoningClient,
    OpenRouterReasoningClient,
    VllmReasoningClient,
    _parse_chat_completion_payload,
    _strip_thinking_blocks,
)

_VALID_DECISION = TriageDecision(
    type=DecisionType.ASK,
    next_feature_id="pregnancy_status",
    question_text="Are you pregnant?",
    citations=("0123456789abcdef",),
    rationale="testing",
)

_VALID_PAYLOAD = {
    "choices": [
        {
            "message": {
                "content": json.dumps(
                    {
                        "type": "ask",
                        "next_feature_id": "pregnancy_status",
                        "question_text": "Are you pregnant?",
                        "citations": ["0123456789abcdef"],
                        "rationale": "testing",
                    }
                )
            }
        }
    ]
}


def test_strip_thinking_blocks_removes_redacted_block() -> None:
    raw = (
        '<think>internal</think>'
        '{"type":"ask","rationale":"x","next_feature_id":"pregnancy_status",'
        '"question_text":"?","citations":["a"]}'
    )
    assert _strip_thinking_blocks(raw).startswith('{"type"')


def test_parse_chat_completion_payload_validates_decision() -> None:
    decision = _parse_chat_completion_payload(_VALID_PAYLOAD)
    assert decision.type is DecisionType.ASK
    assert decision.next_feature_id == "pregnancy_status"


def test_fallback_uses_primary_when_it_succeeds() -> None:
    primary = MagicMock()
    primary.decide.return_value = _VALID_DECISION
    fallback = MagicMock()

    client = FallbackReasoningClient(primary=primary, fallback=fallback)
    result = client.decide(system_prompt="sys", history=[], context=[])

    assert result is _VALID_DECISION
    fallback.decide.assert_not_called()


def test_fallback_uses_openrouter_when_vllm_is_unreachable() -> None:
    conclude = TriageDecision(
        type=DecisionType.CONCLUDE,
        action_code=ActionCode.ROUTINE_APPOINTMENT,
        citations=("0123456789abcdef",),
        rationale="fallback",
    )
    primary = MagicMock()
    primary.decide.side_effect = httpx.ConnectError("connection refused")
    fallback = MagicMock()
    fallback.decide.return_value = conclude

    client = FallbackReasoningClient(primary=primary, fallback=fallback)
    result = client.decide(system_prompt="sys", history=[], context=[])

    assert result.action_code is ActionCode.ROUTINE_APPOINTMENT
    fallback.decide.assert_called_once()


def test_vllm_client_posts_to_chat_completions(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return _VALID_PAYLOAD

    class FakeClient:
        def post(self, url: str, *, headers: dict[str, str], json: dict[str, object]):
            captured["url"] = url
            captured["json"] = json
            return FakeResponse()

    client = VllmReasoningClient(
        base_url="http://gpu-pc:8002",
        model="herhealth",
        client=FakeClient(),  # type: ignore[arg-type]
    )
    decision = client.decide(
        system_prompt="system",
        history=[Message(role="user", content="hello")],
        context=[],
    )

    assert captured["url"] == "http://gpu-pc:8002/v1/chat/completions"
    body = captured["json"]
    assert isinstance(body, dict)
    assert body["model"] == "herhealth"
    assert body["chat_template_kwargs"] == {"enable_thinking": False}
    # Must not request json_object — that path crashes campus vLLM via xgrammar.
    assert "response_format" not in body
    assert decision.type is DecisionType.ASK


def test_openrouter_retries_after_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    calls = {"count": 0}
    bad = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "type": "ask",
                            "rationale": "need more info",
                            "citations": ["0123456789abcdef"],
                            "red_flag_id": None,
                        }
                    )
                }
            }
        ]
    }

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            calls["count"] += 1
            return _VALID_PAYLOAD if calls["count"] > 1 else bad

    class FakeClient:
        def post(self, url: str, *, headers: dict[str, str], json: dict[str, object]):
            return FakeResponse()

    client = OpenRouterReasoningClient(api_key="test-key", client=FakeClient())  # type: ignore[arg-type]
    decision = client.decide(system_prompt="system", history=[], context=[])

    assert calls["count"] == 2
    assert decision.type is DecisionType.ASK


def test_openrouter_client_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        OpenRouterReasoningClient()
