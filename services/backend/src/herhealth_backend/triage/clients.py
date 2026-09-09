"""Real ``ReasoningClient`` / ``RetrievalClient`` implementations — ADR 0012.

Neither class here is imported by ``agent.py``, ``engine.py``, or anything
else in the triage core — only by whoever wires ``TriageAgent`` up for real
(ADR 0012's migration checklist item 4, not started yet). That keeps the
triage core importable with no network, no server and no GPU, exactly as
``services/backend/pyproject.toml`` states as a property worth protecting.
Needs the ``agent`` extra (``httpx``) — not a base dependency, for the same
reason.
"""

from __future__ import annotations

import json
import logging
import os
import re
from collections.abc import Sequence

import httpx
from herhealth_contracts.decision import TriageDecision
from herhealth_contracts.retrieval import RetrievedPassage
from pydantic import TypeAdapter, ValidationError

from herhealth_backend.triage.agent import Message

__all__ = [
    "DEFAULT_MODEL",
    "DEFAULT_VLLM_MODEL",
    "FallbackReasoningClient",
    "HttpRetrievalClient",
    "OPENROUTER_API_KEY_ENV",
    "OpenRouterReasoningClient",
    "VLLM_API_KEY_ENV",
    "VLLM_MODEL_ENV",
    "VLLM_URL_ENV",
    "VllmReasoningClient",
]

logger = logging.getLogger(__name__)

OPENROUTER_API_KEY_ENV = "OPENROUTER_API_KEY"
VLLM_URL_ENV = "HERHEALTH_VLLM_URL"
VLLM_MODEL_ENV = "HERHEALTH_VLLM_MODEL"
VLLM_API_KEY_ENV = "HERHEALTH_VLLM_API_KEY"
_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
_CHAT_COMPLETIONS_PATH = "/v1/chat/completions"

#: The base model, unadapted. NOT the fine-tuned LoRA adapter — OpenRouter
#: serves published models, not this project's private one. Swapping to the
#: retrained adapter (once it exists and is reviewed, per CLAUDE.md) means
#: going back to a self-hosted vLLM server
#: (docs/runbooks/dev-vllm-lora-endpoint.md) and a different concrete
#: ReasoningClient — not editing this string. ReasoningClient being a
#: Protocol is what makes that swap a new class instead of a rewrite of
#: TriageAgent.
DEFAULT_MODEL = "qwen/qwen3.5-9b"

#: The LoRA adapter name as registered with ``vllm serve --lora-modules``.
DEFAULT_VLLM_MODEL = "herhealth"

#: Per-call retries when OpenRouter returns JSON that fails ``TriageDecision``
#: validation — same prompt twice often repeats the mistake; feedback helps.
MAX_DECISION_ATTEMPTS = 3

#: Qwen3.5 thinking blocks may appear in ``content`` when thinking mode is
#: left on — see docs/runbooks/dev-vllm-lora-endpoint.md.
_THINKING_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL)


def _render_context(context: Sequence[RetrievedPassage]) -> str:
    """Retrieved passages, rendered into the system prompt. Mirrors
    ``agent.render_red_flags``'s role for red flags: red flags are injected
    unconditionally, this is injected only when retrieval found something.

    Labelled ``passage_id=`` rather than a bare ``[hash]``, and evidence
    statements' own ``feature_id``/``condition_id`` are surfaced explicitly
    when present — both changes made after a live test
    (2026-09-01) returned a passage's hash where a real feature id
    belonged: ``next_feature_id="14ebb1e7a2e19149"``. A hex hash and a real
    feature id look similar enough in a wall of retrieved text that the
    model conflated the two namespaces; this makes the difference visible
    rather than relying on the instruction text alone to prevent it.
    """
    if not context:
        return "No retrieved passages matched this turn."
    lines = [
        "Retrieved passages. passage_id is ONLY for `citations` — it is a "
        "content hash, never a feature or condition id, even though both "
        "are lowercase strings."
    ]
    for p in context:
        line = f'- passage_id={p.id} ({p.citation}): "{p.text}"'
        if p.feature_id is not None or p.condition_id is not None:
            line += (
                f" [this row: feature_id={p.feature_id}, condition_id={p.condition_id}"
                f", value={p.value}]"
            )
        lines.append(line)
    return "\n".join(lines)


#: Verified empirically (2026-09-01, against OpenRouter's Venice and
#: SiliconFlow routes for this model): ``response_format: {"type":
#: "json_schema", "json_schema": {"strict": true, "schema": <the full
#: TriageDecision schema>}}`` does not fail fast — it hangs indefinitely
#: (killed after 10+ minutes in testing). ``strict: false`` against the same
#: schema avoids the hang but the model spends thousands of tokens
#: "reasoning" about the request instead of answering, and
#: ``chat_template_kwargs.enable_thinking: false`` is inconsistently honoured
#: across OpenRouter's backing providers regardless of which strict setting
#: is used. Plain ``{"type": "json_object"}`` plus an explicit, direct
#: shape instruction in the prompt returned correctly in ~7 seconds in the
#: same testing. This is the documented reason this client does not use
#: ``json_schema``/``strict`` mode even though ADR 0011 describes guided
#: decoding as the intended contract — that guarantee assumed a self-hosted
#: vLLM server's own ``guided_json``, a single first-party implementation,
#: not a heterogeneous aggregation of third-party ones. Pydantic validation
#: on receipt (see :meth:`OpenRouterReasoningClient.decide`) is what actually
#: enforces the schema against this provider.
_JSON_SHAPE_INSTRUCTION = (
    "\n\nRespond with ONLY a single JSON object, no other text, matching this shape: "
    '{"type": "ask", "conclude" or "decline", "rationale": "why, required always — '
    'and for a decline this is also the text she reads, so write it to her", '
    '"next_feature_id": "REQUIRED string when type is ask — must be a real '
    "feature id from the list in the system prompt; null only when type is "
    'conclude", '
    '"question_text": "REQUIRED non-empty string when type is ask — the '
    'clarifying question for the user; null only when type is conclude", '
    '"action_code": "one of SELF_CARE|ROUTINE_APPOINTMENT|URGENT_SAME_DAY|EMERGENCY, '
    'required only if type is conclude, else null", '
    '"matching_conditions": ["array of condition ids, at most 5, only if type is conclude; '
    'use [] not null when empty; '
    'allowed together with red_flag_id ONLY when action_code is EMERGENCY, and required '
    "then if any retrieved passage showed a matching condition_id; at any other urgency a "
    'red-flag-driven conclusion leaves this empty"], '
    '"citations": ["array of bare 16-hex passage ids ONLY — e.g. '
    '\\"a6bf0793b2a9a509\\"; never \\"passage_id=…\\" and never a feature '
    'or condition id; use [] not null"], '
    '"red_flag_id": "a red_flags.yaml id if this decision is driven by one, else null"}. '
    "MANDATORY: citations must be non-empty UNLESS red_flag_id is set — this applies to "
    "an ask as much as a conclude. If you are asking a question because of something a "
    "retrieved passage suggests, cite that passage's id even though you have not "
    "concluded yet. An ask or conclude with empty citations and no red_flag_id is "
    "invalid and will be rejected.\n\n"
    "A DECLINE IS THE EXACT OPPOSITE, and is how you refuse an off-scope message (see "
    "the scope rule at the top of this prompt). type \"decline\" takes ONLY rationale: "
    "next_feature_id, question_text, action_code, matching_conditions, red_flag_id must "
    "all be null and citations MUST be [] — a decline asserts nothing about her health, "
    "so it cites nothing, and a decline carrying any of those fields is invalid and "
    "will be rejected. Do not reach for a retrieved passage to satisfy the citation "
    "rule on a question the passage does not address; decline instead. Do not answer "
    "the off-scope question itself, even if you know the answer.\n\n"
    "THREE DIFFERENT KINDS OF ID — do not mix them up: "
    "(1) passage_id, shown on each retrieved passage above — use these ONLY in "
    "`citations`, never in `next_feature_id` or `matching_conditions`. "
    "(2) feature_id — a real one is shown only when a retrieved passage's own line "
    "says `feature_id=...`; if none of the retrieved passages show a feature_id, you "
    "do not have a real one available and must not invent one — conclude instead of "
    "asking, or ask a general question and pick the closest real feature_id you "
    "already know from earlier in this conversation. "
    "(3) condition_id — same rule: only use one a retrieved passage's `condition_id=` "
    "field actually showed you, never a passage_id or an invented name. "
    "If type is ask, next_feature_id and question_text are BOTH mandatory — "
    "never send ask with only rationale and citations. "
    "If you cannot pick a real feature id and the message is in scope, use type "
    "conclude instead; if it is out of scope, use type decline. "
    "If she asked about a medicine, say in rationale (and in question_text if "
    "you are asking) that you cannot advise on medicines and she should ask a "
    "doctor or pharmacist — never answer the drug question yourself."
)


def _build_messages(
    *,
    system_prompt: str,
    history: Sequence[Message],
    context: Sequence[RetrievedPassage],
    retry_feedback: str = "",
) -> list[dict[str, str]]:
    system_content = (
        f"{system_prompt}\n\n{_render_context(context)}{_JSON_SHAPE_INSTRUCTION}{retry_feedback}"
    )
    return [
        {"role": "system", "content": system_content},
        *({"role": m.role, "content": m.content} for m in history),
    ]


def _strip_thinking_blocks(content: str) -> str:
    return _THINKING_BLOCK.sub("", content).strip()


def _parse_chat_completion_payload(payload: object) -> TriageDecision:
    try:
        assert isinstance(payload, dict)
        content = payload["choices"][0]["message"]["content"]
        assert isinstance(content, str)
        cleaned = _strip_thinking_blocks(content)
        return TriageDecision.model_validate(json.loads(cleaned))
    except (KeyError, IndexError, TypeError, json.JSONDecodeError, ValidationError) as error:
        raise ValueError(f"reasoning model returned malformed JSON: {error}") from error


def _chat_completions_body(
    *,
    model: str,
    messages: list[dict[str, str]],
    enforce_json_object: bool = True,
) -> dict[str, object]:
    """Build the OpenAI-compatible chat body.

    ``response_format: json_object`` is on for OpenRouter. On campus vLLM
    (Qwen3.5 + LoRA, TP=2) that same field turns on xgrammar structured
    outputs; the Triton ``apply_token_bitmask_inplace`` kernel then hits
    ``CUDA: unspecified launch failure``, kills Worker_TP1, and takes the
    whole EngineCore down (observed 2026-09-08 on Lobot). Prompt-shaped JSON
    plus ``TriageDecision.model_validate`` is enough until guided decoding is
    wired deliberately (ADR 0011 checklist item 7).
    """
    body: dict[str, object] = {
        "model": model,
        "messages": messages,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    if enforce_json_object:
        body["response_format"] = {"type": "json_object"}
    return body


def _decide_via_chat_completions(
    *,
    client: httpx.Client,
    url: str,
    headers: dict[str, str],
    model: str,
    system_prompt: str,
    history: Sequence[Message],
    context: Sequence[RetrievedPassage],
    enforce_json_object: bool = True,
) -> TriageDecision:
    """POST /v1/chat/completions with validation retries and error feedback."""
    retry_feedback = ""
    last_error: Exception | None = None
    for attempt in range(1, MAX_DECISION_ATTEMPTS + 1):
        messages = _build_messages(
            system_prompt=system_prompt,
            history=history,
            context=context,
            retry_feedback=retry_feedback,
        )
        body = _chat_completions_body(
            model=model,
            messages=messages,
            enforce_json_object=enforce_json_object,
        )
        response = client.post(url, headers=headers, json=body)
        response.raise_for_status()
        try:
            return _parse_chat_completion_payload(response.json())
        except ValueError as error:
            last_error = error
            if attempt >= MAX_DECISION_ATTEMPTS:
                raise
            retry_feedback = (
                f"\n\nYOUR PREVIOUS JSON WAS REJECTED: {error}\n"
                "Fix it. If type is ask, include BOTH next_feature_id (a real "
                "feature id from the system prompt list) AND question_text. "
                "citations must be bare 16-character hex ids only "
                '(e.g. "a6bf0793b2a9a509"), never "passage_id=…". '
                "Use [] not null for empty arrays. If type is decline, send "
                "rationale only — every other field null, citations []. If you "
                "cannot ask a valid question, use type conclude with action_code "
                "instead, or type decline if the message is out of scope."
            )
            logger.warning(
                "decision attempt %s/%s failed (%s) — retrying with feedback",
                attempt,
                MAX_DECISION_ATTEMPTS,
                error,
            )
    raise ValueError(str(last_error))


class OpenRouterReasoningClient:
    """Implements ``herhealth_backend.triage.agent.ReasoningClient`` against
    OpenRouter's chat-completions API. Requests plain JSON-object output
    (not schema-constrained ``json_schema``/``strict`` mode — see
    ``_JSON_SHAPE_INSTRUCTION``'s comment for why that hangs in practice)
    with the required shape spelled out directly in the prompt.
    ``TriageDecision.model_validate`` on receipt is what actually enforces
    the schema here, not the provider — this is a real gap against ADR
    0011's "guided decoding" guarantee, which assumed a self-hosted vLLM
    server's own constrained decoding, not a plain-JSON request to a
    third-party aggregator. A malformed or out-of-vocabulary response fails
    here, legibly, as a ``pydantic.ValidationError`` — it is not silently
    accepted.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
        client: httpx.Client | None = None,
        # 120s, matching VllmReasoningClient below, because 60s was under the
        # observed latency of this very endpoint: app/triage/routes.py's
        # REASONING_TIMEOUT_SECONDS documents "a few seconds to ~90s across
        # manual testing" and budgets 150s for the whole turn. A 60s read
        # timeout therefore aborted responses that were merely slow, and an
        # httpx timeout is raised as httpx.HTTPError, which that route turns
        # straight into a 502 without a retry — so a healthy 75s answer was
        # indistinguishable to the user from a broken dependency. Confirmed
        # live 2026-09-03: "triage dependency HTTP failure: The read
        # operation timed out" at 116s wall-clock on an in-scope emergency.
        # Keep this below REASONING_TIMEOUT_SECONDS so the inner call fails
        # inside the turn's own budget rather than racing it.
        timeout: float = 120.0,
    ) -> None:
        key = api_key or os.environ.get(OPENROUTER_API_KEY_ENV)
        if not key:
            raise RuntimeError(
                f"{OPENROUTER_API_KEY_ENV} is not set and no api_key was given — "
                "OpenRouterReasoningClient needs an OpenRouter API key."
            )
        self._model = model
        self._client = client or httpx.Client(timeout=timeout)
        self._headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    def decide(
        self,
        *,
        system_prompt: str,
        history: Sequence[Message],
        context: Sequence[RetrievedPassage],
    ) -> TriageDecision:
        return _decide_via_chat_completions(
            client=self._client,
            url=_OPENROUTER_URL,
            headers=self._headers,
            model=self._model,
            system_prompt=system_prompt,
            history=history,
            context=context,
        )


class VllmReasoningClient:
    """Self-hosted vLLM with the project's LoRA adapter (``herhealth``).

    See ``docs/runbooks/dev-vllm-lora-endpoint.md`` and
    ``docs/runbooks/friend-pc-vllm-setup.md``. Uses the same plain-JSON
    contract as :class:`OpenRouterReasoningClient` until guided decoding is
    wired (ADR 0011 migration checklist item 7). Does **not** send
    ``response_format: json_object`` — on the Lobot Qwen3.5 + LoRA serve that
    path crashes the engine via xgrammar/Triton (see
    ``_chat_completions_body``).
    """

    def __init__(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        client: httpx.Client | None = None,
        timeout: float = 120.0,
    ) -> None:
        raw_url = base_url or os.environ.get(VLLM_URL_ENV, "http://127.0.0.1:8002")
        self._url = f"{raw_url.rstrip('/')}{_CHAT_COMPLETIONS_PATH}"
        self._model = model or os.environ.get(VLLM_MODEL_ENV, DEFAULT_VLLM_MODEL)
        self._client = client or httpx.Client(timeout=timeout)
        self._headers = {"Content-Type": "application/json"}
        # vLLM's ``--api-key`` makes it expect the same Bearer scheme
        # OpenRouter uses. Added only when a key exists: an empty
        # Authorization header is worse than none, because a server that
        # requires no key would still see a malformed credential.
        key = api_key or os.environ.get(VLLM_API_KEY_ENV) or None
        if key:
            self._headers["Authorization"] = f"Bearer {key}"

    def decide(
        self,
        *,
        system_prompt: str,
        history: Sequence[Message],
        context: Sequence[RetrievedPassage],
    ) -> TriageDecision:
        return _decide_via_chat_completions(
            client=self._client,
            url=self._url,
            headers=self._headers,
            model=self._model,
            system_prompt=system_prompt,
            history=history,
            context=context,
            enforce_json_object=False,
        )


class FallbackReasoningClient:
    """Try a primary ``ReasoningClient`` (typically vLLM), then a fallback
    (typically OpenRouter) when the primary is unreachable.

  Only connectivity and upstream availability errors trigger the fallback —
  a malformed model response from the primary is re-raised, because that is
  not something a different server can fix.
    """

    def __init__(
        self,
        *,
        primary: OpenRouterReasoningClient | VllmReasoningClient,
        fallback: OpenRouterReasoningClient | VllmReasoningClient,
        primary_name: str = "vllm",
        fallback_name: str = "openrouter",
    ) -> None:
        self._primary = primary
        self._fallback = fallback
        self._primary_name = primary_name
        self._fallback_name = fallback_name

    def decide(
        self,
        *,
        system_prompt: str,
        history: Sequence[Message],
        context: Sequence[RetrievedPassage],
    ) -> TriageDecision:
        try:
            return self._primary.decide(
                system_prompt=system_prompt, history=history, context=context
            )
        except httpx.HTTPStatusError as error:
            if error.response.status_code not in {502, 503, 504}:
                raise
            logger.warning(
                "%s returned HTTP %s — falling back to %s",
                self._primary_name,
                error.response.status_code,
                self._fallback_name,
            )
        except (httpx.ConnectError, httpx.TimeoutException) as error:
            logger.warning(
                "%s unreachable (%s) — falling back to %s",
                self._primary_name,
                error,
                self._fallback_name,
            )

        return self._fallback.decide(
            system_prompt=system_prompt, history=history, context=context
        )


class HttpRetrievalClient:
    """Implements ``herhealth_backend.triage.agent.RetrievalClient`` against
    ``services/model``'s ``/search`` endpoint. Never imports
    ``herhealth_data`` — the whole reason that service exists is so this
    client does not have to (import-linter forbids it across this boundary).
    """

    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:8001",
        client: httpx.Client | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = client or httpx.Client(timeout=timeout)

    def search(self, query: str, *, k: int = 8) -> list[RetrievedPassage]:
        response = self._client.post(f"{self._base_url}/search", json={"query": query, "k": k})
        response.raise_for_status()
        return TypeAdapter(list[RetrievedPassage]).validate_python(response.json())
