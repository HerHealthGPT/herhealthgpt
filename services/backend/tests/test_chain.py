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


# --- the extract step ---------------------------------------------------------

from pathlib import Path  # noqa: E402

from herhealth_contracts.loading import load_knowledge_base  # noqa: E402

from herhealth_backend.triage.chain import (  # noqa: E402
    LangChainAnswerWriter,
    LangChainFeatureExtractor,
    carry_warning_lines,
    trim_adapter_answer,
)

KNOWLEDGE = load_knowledge_base(Path(__file__).resolve().parents[3] / "knowledge")
SAID = [Message(role="user", content="my periods are all over the place")]


def _extractor(script: Scripted) -> LangChainFeatureExtractor:
    return LangChainFeatureExtractor(RunnableLambda(script), KNOWLEDGE)


def test_extraction_maps_a_message_to_listed_values() -> None:
    script = Scripted('{"cycle_regularity": "irregular"}')
    assert _extractor(script).extract(SAID, pending_feature=None) == {
        "cycle_regularity": "irregular"
    }
    prompt = script.seen[0][0].content
    assert "cycle_regularity" in prompt and "irregular" in prompt
    assert "my periods are all over the place" in script.seen[0][-1].content


def test_unknown_features_and_values_are_dropped() -> None:
    script = Scripted('{"cycle_regularity": "wobbly", "made_up": "yes", "fever": "yes"}')
    assert _extractor(script).extract(SAID, pending_feature=None) == {"fever": "yes"}


@pytest.mark.parametrize("reply", ["not json", "[1, 2]", _timeout()])
def test_a_failed_extraction_returns_nothing(reply: Any) -> None:
    assert _extractor(Scripted(reply)).extract(SAID, pending_feature=None) == {}


def test_the_pending_question_is_named_in_the_prompt() -> None:
    script = Scripted("{}")
    _extractor(script).extract(SAID, pending_feature="cycle_length")
    assert "cycle_length" in script.seen[0][-1].content


# --- the answer step ----------------------------------------------------------

BASE_ANSWER = (
    "Explanation.\n\nWhen to get medical help:\n"
    "- Get emergency care now if the pain is sudden.\n"
    "- See someone today if you have a fever."
)


def test_sources_section_is_trimmed() -> None:
    text = "An answer.\n\n**Sources:**\n- first\n- second"
    assert trim_adapter_answer(text) == "An answer."


def test_markdown_emphasis_is_stripped() -> None:
    assert trim_adapter_answer("### Heading\nThis is **important** and __clear__.") == (
        "Heading\nThis is important and clear."
    )


def test_warning_lines_are_appended_when_missing() -> None:
    out = carry_warning_lines("The adapter's answer.", BASE_ANSWER)
    assert out.startswith("The adapter's answer.\n\nWhen to get medical help:\n")
    assert "- Get emergency care now if the pain is sudden." in out
    assert "- See someone today if you have a fever." in out


def test_warning_lines_are_not_duplicated() -> None:
    already = (
        "An answer.\n- Get emergency care now if the pain is sudden.\n"
        "- See someone today if you have a fever."
    )
    assert carry_warning_lines(already, BASE_ANSWER) == already


def test_an_answer_with_no_warning_lines_to_carry_is_unchanged() -> None:
    result = carry_warning_lines("An answer.", "A base answer with nothing else in it.")
    assert result == "An answer."


def _writer(script: Scripted) -> LangChainAnswerWriter:
    return LangChainAnswerWriter(RunnableLambda(script), name="herhealth")


def test_the_writer_returns_a_cleaned_answer_with_warning_lines() -> None:
    script = Scripted("A supportive answer.\n\nSources:\n- x")
    out = _writer(script).write("what is it?", [PASSAGE], BASE_ANSWER)
    assert out is not None and out.startswith("A supportive answer.\n\nWhen to get medical help:")
    user = script.seen[0][-1].content
    assert "A placeholder passage." in user and "what is it?" in user


@pytest.mark.parametrize(
    "reply",
    ["", "   ", "x" * 3000, "You mentioned that this is not a diagnosis.", _timeout()],
)
def test_an_unusable_answer_returns_none(reply: Any) -> None:
    assert _writer(Scripted(reply)).write("q", [PASSAGE], BASE_ANSWER) is None


# --- found in review: warning signs in other shapes ----------------------------

HEADED = (
    "Explanation.\n\nGet emergency care now if:\n- the pain is sudden\n- you feel faint\n\n"
    "See someone today if:\n- you have a fever"
)


def test_a_heading_with_bullets_is_carried_with_its_conditions() -> None:
    out = carry_warning_lines("The adapter's answer.", HEADED)
    assert out is not None
    for line in (
        "Get emergency care now if:",
        "- the pain is sudden",
        "- you feel faint",
        "See someone today if:",
        "- you have a fever",
    ):
        assert line in out


@pytest.mark.parametrize(
    "base_answer",
    [
        "Explanation.\n\nSeek emergency care immediately if the pain is sudden.",
        "Explanation.\n\nWhen to get medical help:\n- Go to hospital urgently if you feel faint.",
    ],
)
def test_urgent_advice_in_other_words_makes_the_base_answer_stand(base_answer: str) -> None:
    # The lines cannot be recognised well enough to carry, so the adapter's
    # text must not replace an answer that contains urgent advice.
    assert carry_warning_lines("The adapter's answer.", base_answer) is None
    assert _writer(Scripted("A supportive answer.")).write("q", [PASSAGE], base_answer) is None


# --- an invented name in the model's own notes ----------------------------------


def test_unknown_notes_are_dropped_before_validation() -> None:
    from herhealth_backend.triage.provenance import drop_unknown_observed

    reply = json.dumps(
        {
            "type": "ask",
            "rationale": "One more detail would help.",
            "next_feature_id": "cycle_length",
            "question_text": "How many days are there between your periods?",
            "observed": {
                "dark_velvety_patches": "yes",
                "cycle_regularity": "wobbly",
                "fever": "yes",
                "pain_with_sex": "unknown",
            },
        }
    )

    def validator(decision: TriageDecision, context: Sequence[RetrievedPassage]) -> None:
        assert dict(decision.observed) == {"fever": "yes", "pain_with_sex": "unknown"}

    script = Scripted(reply)
    client = LangChainReasoningClient(
        RunnableLambda(script),
        name="m",
        validator=validator,
        repair=lambda decision: drop_unknown_observed(decision, KNOWLEDGE),
    )
    result = client.decide(system_prompt="S", history=HISTORY, context=[PASSAGE])
    assert dict(result.decision.observed) == {"fever": "yes", "pain_with_sex": "unknown"}
    assert len(script.seen) == 1


# --- a reply rejected only for its wording gets one more attempt ----------------

CASE_NOTE = "You mentioned something outside this tool's scope."


def test_a_wording_failure_gets_one_extra_attempt_with_specific_feedback() -> None:
    script = Scripted(_decline(CASE_NOTE), _decline(CASE_NOTE), _decline())
    result = _decide(_client(script, max_attempts=2))
    assert result.decision.rationale.startswith("This tool covers")
    assert len(script.seen) == 3
    final_prompt = script.seen[2][0].content
    assert "ONLY problem is the wording" in final_prompt
    assert "You mentioned" in final_prompt


def test_three_wording_failures_still_raise() -> None:
    script = Scripted(_decline(CASE_NOTE), _decline(CASE_NOTE), _decline(CASE_NOTE))
    with pytest.raises(ValueError, match="internal machinery"):
        _decide(_client(script, max_attempts=2))
    assert len(script.seen) == 3


def test_other_failures_do_not_get_the_extra_attempt() -> None:
    script = Scripted("prose", "prose", _decline())
    with pytest.raises(ValueError, match="no JSON object"):
        _decide(_client(script, max_attempts=2))
    assert len(script.seen) == 2


def test_symptom_topics_keep_only_listed_feature_ids() -> None:
    from pathlib import Path

    from herhealth_contracts.loading import load_knowledge_base
    from langchain_core.language_models.fake_chat_models import FakeListChatModel

    from herhealth_backend.triage.chain import LangChainSymptomTopics

    base = load_knowledge_base(Path(__file__).resolve().parents[3] / "knowledge")
    reply = '{"features": ["pelvic_pain_severity", "invented_feature", "pelvic_pain_severity"]}'
    reader = LangChainSymptomTopics(FakeListChatModel(responses=[reply]), base)

    assert reader.mentioned("What if my period pain is severe?") == ("pelvic_pain_severity",)


def test_symptom_topics_return_nothing_on_a_bad_reply() -> None:
    from pathlib import Path

    from herhealth_contracts.loading import load_knowledge_base
    from langchain_core.language_models.fake_chat_models import FakeListChatModel

    from herhealth_backend.triage.chain import LangChainSymptomTopics

    base = load_knowledge_base(Path(__file__).resolve().parents[3] / "knowledge")
    reader = LangChainSymptomTopics(FakeListChatModel(responses=["no json here"]), base)

    assert reader.mentioned("anything") == ()
