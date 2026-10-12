"""The reasoning chain: the local models, called through LangChain.

Three small components, each behind a seam ``TriageAgent`` owns:

* :class:`LangChainReasoningClient` — the decide step. One reply in, one
  validated ``TriageDecision`` out, with the error fed back on a retry.

The models are served by vLLM and reached over its OpenAI-compatible
endpoint (``scripts/serve-models.sh``); nothing is loaded in this process.
The prompt text, the passage rendering and every check live in
``triage/clients.py`` and are reused here unchanged: this module decides how
the model is *called*, not what it is told. See ADR 0018.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

import httpx
import openai
from herhealth_contracts.retrieval import RetrievedPassage
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from herhealth_backend.triage.agent import (
    AttemptOutcome,
    Message,
    ReasoningAttempt,
    ReasoningResult,
)
from herhealth_backend.triage.clients import (
    DecisionValidator,
    _build_messages,
    _reject_leaked_internals,
    extract_json_object,
    parse_decision_text,
    retry_feedback,
)

__all__ = [
    "LangChainReasoningClient",
    "ReasoningUnavailable",
    "build_chat_model",
    "extract_json_object",
]

logger = logging.getLogger(__name__)


class ReasoningUnavailable(httpx.HTTPError):
    """The chat endpoint could not be reached, or did not answer in time.

    An ``httpx.HTTPError`` on purpose: the turn route already maps that to
    502 "a service we rely on is temporarily unavailable". The OpenAI client
    raises its own exception types, which would otherwise surface as a 500.
    """


def build_chat_model(
    *, url: str, model: str, api_key: str | None, timeout: float, max_tokens: int
) -> Any:
    """A chat model served by vLLM.

    ``temperature=0`` so the same input gives the same reply: with sampling
    on, an identical turn was observed valid in one run and prose in the
    next. ``max_tokens`` is always set; without it vLLM allows whatever is
    left of the window. ``max_retries=0`` because retrying is this module's
    job, and a blind resend repeats the mistake.
    """
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=model,
        base_url=f"{url.rstrip('/')}/v1",
        api_key=api_key or "not-needed",
        temperature=0,
        max_tokens=max_tokens,
        timeout=timeout,
        max_retries=0,
        # Qwen3.5 otherwise spends its output budget on a thinking block.
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
    )


def _to_messages(raw: Sequence[dict[str, str]]) -> list[BaseMessage]:
    kinds = {"system": SystemMessage, "user": HumanMessage, "assistant": AIMessage}
    return [kinds[message["role"]](content=message["content"]) for message in raw]


def _text(reply: object) -> object:
    return getattr(reply, "content", reply)


def _invoke(chat: Any, messages: Sequence[BaseMessage], *, what: str) -> object:
    """One call. A timeout is re-raised as itself so callers can retry it;
    any other transport failure becomes :class:`ReasoningUnavailable`."""
    try:
        return _text(chat.invoke(list(messages)))
    except openai.APITimeoutError:
        raise
    except (openai.OpenAIError, OSError) as error:
        raise ReasoningUnavailable(f"the {what} model is unavailable: {error}") from error


class LangChainReasoningClient:
    """Implements ``herhealth_backend.triage.agent.ReasoningClient``."""

    def __init__(
        self,
        chat: Any,
        *,
        name: str,
        validator: DecisionValidator | None = None,
        max_attempts: int = 2,
    ) -> None:
        self._chat = chat
        self._name = name
        self._validator = validator
        self._max_attempts = max(1, max_attempts)

    @property
    def name(self) -> str:
        return self._name

    def decide(
        self,
        *,
        system_prompt: str,
        history: Sequence[Message],
        context: Sequence[RetrievedPassage],
    ) -> ReasoningResult:
        feedback = ""
        for attempt in range(1, self._max_attempts + 1):
            messages = _to_messages(
                _build_messages(
                    system_prompt=system_prompt,
                    history=history,
                    context=context,
                    retry_feedback=feedback,
                )
            )
            try:
                reply = _invoke(self._chat, messages, what="reasoning")
            except openai.APITimeoutError as error:
                # A slow answer is not a broken one: latency for an identical
                # request varies widely on these cards, so the next attempt
                # is often fast.
                if attempt >= self._max_attempts:
                    raise ReasoningUnavailable(
                        f"the reasoning model did not answer in time ({self._max_attempts} "
                        "attempt(s))"
                    ) from error
                logger.warning(
                    "reasoning request timed out (attempt %d/%d) — retrying",
                    attempt,
                    self._max_attempts,
                )
                continue
            try:
                decision = parse_decision_text(reply)
                _reject_leaked_internals(decision)
                if self._validator is not None:
                    self._validator(decision, context)
            except ValueError as error:
                if attempt >= self._max_attempts:
                    raise
                feedback = retry_feedback(error, context)
                logger.warning(
                    "decision attempt %s/%s failed (%s) — retrying with feedback",
                    attempt,
                    self._max_attempts,
                    error,
                )
                continue
            return ReasoningResult(
                decision=decision,
                attempts=(ReasoningAttempt(client=self._name, outcome=AttemptOutcome.OK),),
            )
        raise AssertionError("unreachable: the loop returns or raises")
