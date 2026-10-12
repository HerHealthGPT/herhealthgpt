"""The reasoning chain: the local models, called through LangChain.

Three small components, each behind a seam ``TriageAgent`` owns:

* :class:`LangChainFeatureExtractor` — the extract step. Her latest message
  in, the feature values it states out. Never fails a turn.
* :class:`LangChainReasoningClient` — the decide step. One reply in, one
  validated ``TriageDecision`` out, with the error fed back on a retry.
* :class:`LangChainAnswerWriter` — the answer step. The fine-tuned adapter
  words an informational answer from the cited passages. Never fails a turn,
  and never touches an action code.

The models are served by vLLM and reached over its OpenAI-compatible
endpoint (``scripts/serve-models.sh``); nothing is loaded in this process.
The prompt text, the passage rendering and every check live in
``triage/clients.py`` and are reused here unchanged: this module decides how
the model is *called*, not what it is told. See ADR 0018.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable, Sequence
from typing import Any

import httpx
import openai
from herhealth_contracts.decision import TriageDecision
from herhealth_contracts.knowledge import KnowledgeBase
from herhealth_contracts.retrieval import RetrievedPassage
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from herhealth_backend.triage.agent import (
    AttemptOutcome,
    Message,
    ReasoningAttempt,
    ReasoningResult,
)
from herhealth_backend.triage.clients import (
    _LEAKED_INTERNALS,
    DecisionValidator,
    WordingRejected,
    _build_messages,
    _reject_leaked_internals,
    extract_json_object,
    parse_decision_text,
    retry_feedback,
)

__all__ = [
    "LangChainAnswerWriter",
    "LangChainFeatureExtractor",
    "LangChainReasoningClient",
    "ReasoningUnavailable",
    "build_chat_model",
    "carry_warning_lines",
    "extract_json_object",
    "trim_adapter_answer",
]

logger = logging.getLogger(__name__)

#: Output budgets per step. Always sent: without one vLLM allows whatever is
#: left of the window, which turned an oversized prompt into a retry loop.
EXTRACT_MAX_TOKENS = 300
DECIDE_MAX_TOKENS = 1200
ANSWER_MAX_TOKENS = 900


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
        repair: Callable[[TriageDecision], TriageDecision] | None = None,
    ) -> None:
        self._chat = chat
        self._name = name
        self._validator = validator
        #: Applied to a parsed reply before it is checked. For repairs that
        #: only ever remove something optional; see ``triage/provenance.py``.
        self._repair = repair
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
        # One attempt beyond the limit, used only when the last failure was
        # wording alone: the decision in that reply was sound.
        limit = self._max_attempts
        attempt = 0
        while attempt < limit:
            attempt += 1
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
                if attempt >= limit:
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
                if self._repair is not None:
                    decision = self._repair(decision)
                _reject_leaked_internals(decision)
                if self._validator is not None:
                    self._validator(decision, context)
            except WordingRejected as error:
                if attempt == self._max_attempts and limit == self._max_attempts:
                    limit += 1
                if attempt >= limit:
                    raise
                feedback = retry_feedback(error, context) + (
                    f"\nThe ONLY problem is the wording of {error.field}: it contains "
                    f"{error.phrase!r}. Keep every other field exactly as it was. Rewrite "
                    f"{error.field} so it does not refer to what she said, reported or "
                    'mentioned at all: name the symptom itself, as in "Pain this severe '
                    'with a fever" rather than "You reported severe pain and a fever".'
                )
                logger.warning(
                    "decision attempt %s/%s failed on wording (%s) — retrying",
                    attempt,
                    limit,
                    error.phrase,
                )
                continue
            except ValueError as error:
                if attempt >= limit:
                    raise
                feedback = retry_feedback(error, context)
                logger.warning(
                    "decision attempt %s/%s failed (%s) — retrying with feedback",
                    attempt,
                    limit,
                    error,
                )
                continue
            return ReasoningResult(
                decision=decision,
                attempts=(ReasoningAttempt(client=self._name, outcome=AttemptOutcome.OK),),
            )
        raise AssertionError("unreachable: the loop returns or raises")


# ---------------------------------------------------------------------------
# The extract step
# ---------------------------------------------------------------------------

_EXTRACT_INSTRUCTIONS = (
    "You record what a woman has just said about HERSELF, so that a later step "
    "can decide what to ask her. Below is a list of features, each with the only "
    "values it may take. Read her message and reply with ONE JSON object that "
    "maps a feature id to one of that feature's listed values, for every feature "
    "her message states about her own body or situation. Everyday, indirect and "
    "emotional wording counts: map what she means onto the closest listed value. "
    "Include a feature only when her message actually says it. A general question "
    "about a subject, with nothing about herself, is {}. Never guess, never add a "
    "feature she did not mention, and never write anything outside the JSON object."
)


class LangChainFeatureExtractor:
    """Implements ``herhealth_backend.triage.agent.FeatureExtractor``."""

    def __init__(self, chat: Any, base: KnowledgeBase) -> None:
        self._chat = chat
        self._allowed = {
            feature.id: {str(value) for value in feature.allowed_values}
            for feature in base.features
            if feature.allowed_values
        }
        listing = "\n".join(
            f"- {feature.id} ({feature.label}): "
            + " | ".join(str(value) for value in feature.allowed_values)
            for feature in base.features
            if feature.allowed_values
        )
        self._system = f"{_EXTRACT_INSTRUCTIONS}\n\nFEATURES:\n{listing}"

    def extract(self, history: Sequence[Message], *, pending_feature: str | None) -> dict[str, str]:
        latest = next((m.content for m in reversed(history) if m.role == "user"), "")
        if not latest.strip():
            return {}
        question = next((m.content for m in reversed(history) if m.role == "assistant"), None)
        parts = []
        if pending_feature:
            asked = f': "{question}"' if question else "."
            parts.append(
                f"She was just asked about {pending_feature}{asked} "
                "Her message below is her reply to that."
            )
        parts.append(f'Her message: "{latest}"')
        try:
            reply = _invoke(
                self._chat,
                [SystemMessage(content=self._system), HumanMessage(content="\n\n".join(parts))],
                what="extraction",
            )
            raw = json.loads(extract_json_object(str(reply)))
        except (openai.APITimeoutError, ReasoningUnavailable, ValueError) as error:
            # Nothing recorded is today's behaviour; a failed turn would be worse.
            logger.warning("feature extraction failed, continuing without it: %s", error)
            return {}
        if not isinstance(raw, dict):
            return {}
        return {
            str(feature_id): str(value)
            for feature_id, value in raw.items()
            if str(value) in self._allowed.get(str(feature_id), ())
        }


# ---------------------------------------------------------------------------
# The answer step
# ---------------------------------------------------------------------------

#: The instruction every row of the adapter's training data carried
#: (``ft_corpus_v1.jsonl``), word for word, so it is asked to do exactly what
#: it was trained to do.
ADAPTER_INSTRUCTION = (
    "You are a supportive women's-health information assistant. Answer the "
    "patient's question clearly and safely, and recommend seeing a clinician for "
    "diagnosis or treatment decisions."
)

_ANSWER_FORMAT = (
    "Use ONLY the passages given. If they do not cover part of the question, say "
    "which part you cannot speak to. Write plain text in short paragraphs; start a "
    'line with "- " for a list item. Do not add a list of sources.'
)

#: Longest answer accepted, in characters. The interface shows it in one bubble.
MAX_ANSWER_CHARS = 2500

_SOURCES_HEADING = re.compile(r"^\s*[#*_\s]*sources?\s*:?[*_\s]*:?\s*$", re.IGNORECASE)
_WARNING_LINE = re.compile(r"get emergency care now if|see someone today if", re.IGNORECASE)


def trim_adapter_answer(text: str) -> str:
    """Cut a trailing "Sources:" section and strip markdown emphasis.

    The adapter was trained to end with a source list; the interface renders
    citations itself, and strips markdown, so both would only be noise.
    """
    kept: list[str] = []
    for line in text.splitlines():
        if _SOURCES_HEADING.match(line):
            break
        kept.append(re.sub(r"^\s*#+\s*", "", line).replace("**", "").replace("__", ""))
    return "\n".join(kept).strip()


def _normalise(text: str) -> str:
    return " ".join(text.lower().split())


#: Wording that means the base answer contains urgent advice, whether or not
#: it is phrased the way the prompt asks.
_URGENT_ADVICE = re.compile(
    r"emergency|urgent|right away|straight away|immediately|see someone today"
    r"|when to (get|seek) (medical )?help|call an ambulance",
    re.IGNORECASE,
)


def carry_warning_lines(answer: str, base_answer: str) -> str | None:
    """The answer with the decision model's warning-sign lines appended, or
    ``None`` when they cannot be carried safely.

    The decide prompt makes the base model end an informational answer with
    lines such as "Get emergency care now if…". Those are the most important
    lines in it, so they are copied over by code, verbatim, and never left to
    the adapter to reproduce. Both shapes the prompt's layout rules allow are
    handled: a self-contained line, and a heading ending in a colon followed
    by bullets, which is carried with its bullets.

    ``None`` means the base answer contains urgent advice in a form this
    cannot recognise line by line. The adapter's text must then not replace
    it: the caller keeps the base answer whole.
    """
    present = _normalise(answer)
    lines = base_answer.splitlines()
    blocks: list[list[str]] = []
    index = 0
    while index < len(lines):
        cleaned = lines[index].strip().lstrip("-• ").strip()
        index += 1
        if not cleaned or not _WARNING_LINE.search(cleaned):
            continue
        if not cleaned.endswith(":"):
            blocks.append([f"- {cleaned}"])
            continue
        block = [cleaned]
        while index < len(lines) and lines[index].strip().startswith(("-", "•")):
            block.append("- " + lines[index].strip().lstrip("-• ").strip())
            index += 1
        if len(block) > 1:
            blocks.append(block)

    if not blocks:
        return None if _URGENT_ADVICE.search(base_answer) else answer

    missing = [
        block
        for block in blocks
        if not all(_normalise(line.lstrip("- ")) in present for line in block)
    ]
    if not missing:
        return answer
    carried = "\n\n".join("\n".join(block) for block in missing)
    return f"{answer}\n\nWhen to get medical help:\n{carried}"


class LangChainAnswerWriter:
    """Implements ``herhealth_backend.triage.agent.AnswerWriter``."""

    def __init__(self, chat: Any, *, name: str) -> None:
        self._chat = chat
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def write(
        self, question: str, passages: Sequence[RetrievedPassage], base_answer: str
    ) -> str | None:
        listed = "\n".join(f"- {passage.text}" for passage in passages)
        try:
            reply = _invoke(
                self._chat,
                [
                    SystemMessage(content=f"{ADAPTER_INSTRUCTION} {_ANSWER_FORMAT}"),
                    HumanMessage(content=f"Passages:\n{listed}\n\nQuestion: {question}"),
                ],
                what="answer",
            )
        except (openai.APITimeoutError, ReasoningUnavailable) as error:
            logger.warning(
                "the answer model failed; keeping the decision model's answer: %s", error
            )
            return None
        text = trim_adapter_answer(str(reply))
        if not text or len(text) > MAX_ANSWER_CHARS:
            logger.warning(
                "the answer model's reply was empty or too long; keeping the base answer"
            )
            return None
        for pattern in _LEAKED_INTERNALS:
            if pattern.search(text):
                logger.warning(
                    "the answer model's reply used banned wording; keeping the base answer"
                )
                return None
        carried = carry_warning_lines(text, base_answer)
        if carried is None:
            logger.warning(
                "the base answer holds urgent advice that could not be carried over; keeping it"
            )
        return carried
