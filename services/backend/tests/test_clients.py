"""Unit tests for reasoning clients — connectivity fallback and parsing."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import httpx
import pytest
from herhealth_contracts.decision import DecisionType, TriageDecision
from herhealth_contracts.knowledge import ActionCode

from herhealth_backend.triage.agent import AttemptOutcome, Message, ReasoningResult
from herhealth_backend.triage.clients import (
    FallbackReasoningClient,
    OpenRouterReasoningClient,
    VllmReasoningClient,
    _parse_chat_completion_payload,
    _reject_leaked_internals,
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
    primary.name = "vllm:herhealth"
    primary.decide.return_value = ReasoningResult(decision=_VALID_DECISION)
    fallback = MagicMock()
    fallback.name = "openrouter:base"

    client = FallbackReasoningClient(primary=primary, fallback=fallback)
    result = client.decide(system_prompt="sys", history=[], context=[])

    assert result.decision is _VALID_DECISION
    fallback.decide.assert_not_called()
    assert result.served_by == "vllm:herhealth"
    assert [a.outcome for a in result.attempts] == [AttemptOutcome.OK]


def test_fallback_uses_openrouter_when_vllm_is_unreachable() -> None:
    conclude = TriageDecision(
        type=DecisionType.CONCLUDE,
        action_code=ActionCode.ROUTINE_APPOINTMENT,
        citations=("0123456789abcdef",),
        rationale="fallback",
    )
    primary = MagicMock()
    primary.name = "vllm:herhealth"
    primary.decide.side_effect = httpx.ConnectError("connection refused")
    fallback = MagicMock()
    fallback.name = "openrouter:base"
    fallback.decide.return_value = ReasoningResult(decision=conclude)

    client = FallbackReasoningClient(primary=primary, fallback=fallback)
    result = client.decide(system_prompt="sys", history=[], context=[])

    assert result.decision.action_code is ActionCode.ROUTINE_APPOINTMENT
    fallback.decide.assert_called_once()

    # The whole point of the trail: the turn is attributable to the model that
    # actually answered, and the one that failed is still named.
    assert result.served_by == "openrouter:base"
    assert [(a.client, a.outcome) for a in result.attempts] == [
        ("vllm:herhealth", AttemptOutcome.UNREACHABLE),
        ("openrouter:base", AttemptOutcome.OK),
    ]


@pytest.mark.parametrize(
    "rationale",
    [
        "Please go to an emergency room now or call your local emergency number.",
        "This is a medical emergency — do not wait.",
        "Bleeding in pregnancy is best checked right away.",
        "Heavy bleeding with faintness needs same-day care.",
    ],
)
def test_reject_leaked_internals_allows_ordinary_english(rationale: str) -> None:
    """The words a real answer needs must not trip the guard. "emergency room"
    is the correct thing to say; only the all-caps code is machine leakage.
    """
    _reject_leaked_internals(
        TriageDecision(
            type=DecisionType.CONCLUDE,
            action_code=ActionCode.EMERGENCY,
            citations=("0123456789abcdef",),
            rationale=rationale,
        )
    )


@pytest.mark.parametrize(
    "rationale",
    [
        "This matches a red-flag warning: pelvic pain with faintness or collapse",
        "CODE EMERGENCY",
        "action_code: URGENT_SAME_DAY",
        "matched red_flag_id pelvic_pain_with_fever",
        "see passage_id a6bf0793b2a9a509 for details",
        "I set matching_conditions to endometriosis",
    ],
)
def test_reject_leaked_internals_flags_machine_text(rationale: str) -> None:
    """Every string here is text this system actually produced, or a direct
    variant of it. ``rationale`` is rendered to the user verbatim, so these
    must fail validation and be retried rather than displayed.
    """
    with pytest.raises(ValueError, match="internal machinery"):
        _reject_leaked_internals(
            TriageDecision(
                type=DecisionType.CONCLUDE,
                action_code=ActionCode.EMERGENCY,
                citations=("0123456789abcdef",),
                rationale=rationale,
            )
        )


def test_reject_leaked_internals_checks_question_text_too() -> None:
    with pytest.raises(ValueError, match="question_text"):
        _reject_leaked_internals(
            TriageDecision(
                type=DecisionType.ASK,
                next_feature_id="pregnancy_status",
                question_text="To check the red flag rule, are you pregnant?",
                citations=("0123456789abcdef",),
                rationale="Checking whether pregnancy applies.",
            )
        )


def test_fallback_uses_openrouter_when_primary_returns_no_valid_decision() -> None:
    """The fine-tuned adapter's dominant failure is not being unreachable — it
    is answering with JSON that never validates (an ``ask`` with empty
    ``citations``, measured at roughly one turn in four on 2026-09-09). The
    client raises ``ValueError`` once its own retries are spent, and the base
    model is a genuinely different model that can succeed where it failed.
    """
    conclude = TriageDecision(
        type=DecisionType.CONCLUDE,
        action_code=ActionCode.ROUTINE_APPOINTMENT,
        citations=("0123456789abcdef",),
        rationale="fallback",
    )
    primary = MagicMock()
    primary.name = "vllm:herhealth"
    primary.decide.side_effect = ValueError(
        "reasoning model returned malformed JSON: a decision must be grounded "
        "in at least one citation or a red_flag_id"
    )
    fallback = MagicMock()
    fallback.name = "openrouter:base"
    fallback.decide.return_value = ReasoningResult(decision=conclude)

    client = FallbackReasoningClient(primary=primary, fallback=fallback)
    result = client.decide(system_prompt="sys", history=[], context=[])

    assert result.decision.action_code is ActionCode.ROUTINE_APPOINTMENT
    fallback.decide.assert_called_once()
    assert result.attempts[0].outcome is AttemptOutcome.INVALID_DECISION
    assert "malformed JSON" in (result.attempts[0].detail or "")


def test_fallback_reraises_client_error_statuses_without_calling_fallback() -> None:
    """A 400/401 is a bug in our request, not a sick server. Retrying it
    against a second provider would hide the bug and bill for it twice.
    """
    primary = MagicMock()
    primary.name = "vllm:herhealth"
    primary.decide.side_effect = httpx.HTTPStatusError(
        "unauthorized",
        request=httpx.Request("POST", "http://x/v1/chat/completions"),
        response=httpx.Response(401),
    )
    fallback = MagicMock()

    client = FallbackReasoningClient(primary=primary, fallback=fallback)
    with pytest.raises(httpx.HTTPStatusError):
        client.decide(system_prompt="sys", history=[], context=[])

    fallback.decide.assert_not_called()


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
    ).decision

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
    decision = client.decide(system_prompt="system", history=[], context=[]).decision

    assert calls["count"] == 2
    assert decision.type is DecisionType.ASK


def test_openrouter_client_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        OpenRouterReasoningClient()
