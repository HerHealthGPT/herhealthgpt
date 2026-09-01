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
import os
from collections.abc import Sequence

import httpx
from herhealth_contracts.decision import TriageDecision
from herhealth_contracts.retrieval import RetrievedPassage
from pydantic import TypeAdapter

from herhealth_backend.triage.agent import Message

__all__ = [
    "DEFAULT_MODEL",
    "OPENROUTER_API_KEY_ENV",
    "HttpRetrievalClient",
    "OpenRouterReasoningClient",
]

OPENROUTER_API_KEY_ENV = "OPENROUTER_API_KEY"
_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

#: The base model, unadapted. NOT the fine-tuned LoRA adapter — OpenRouter
#: serves published models, not this project's private one. Swapping to the
#: retrained adapter (once it exists and is reviewed, per CLAUDE.md) means
#: going back to a self-hosted vLLM server
#: (docs/runbooks/dev-vllm-lora-endpoint.md) and a different concrete
#: ReasoningClient — not editing this string. ReasoningClient being a
#: Protocol is what makes that swap a new class instead of a rewrite of
#: TriageAgent.
DEFAULT_MODEL = "qwen/qwen3.5-9b"


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
    '{"type": "ask" or "conclude", "rationale": "why, required always", '
    '"next_feature_id": "a feature id, required only if type is ask, else null", '
    '"question_text": "the question, required only if type is ask, else null", '
    '"action_code": "one of SELF_CARE|ROUTINE_APPOINTMENT|URGENT_SAME_DAY|EMERGENCY, '
    'required only if type is conclude, else null", '
    '"matching_conditions": ["array of condition ids, at most 5, only if type is conclude '
    'and red_flag_id is null, else empty"], '
    '"citations": ["array of retrieved-passage ids this decision is grounded on"], '
    '"red_flag_id": "a red_flags.yaml id if this decision is driven by one, else null"}. '
    "MANDATORY: citations must be non-empty UNLESS red_flag_id is set — this applies to "
    "an ask as much as a conclude. If you are asking a question because of something a "
    "retrieved passage suggests, cite that passage's id even though you have not "
    "concluded yet. A decision with empty citations and no red_flag_id is invalid and "
    "will be rejected.\n\n"
    "THREE DIFFERENT KINDS OF ID — do not mix them up: "
    "(1) passage_id, shown on each retrieved passage above — use these ONLY in "
    "`citations`, never in `next_feature_id` or `matching_conditions`. "
    "(2) feature_id — a real one is shown only when a retrieved passage's own line "
    "says `feature_id=...`; if none of the retrieved passages show a feature_id, you "
    "do not have a real one available and must not invent one — conclude instead of "
    "asking, or ask a general question and pick the closest real feature_id you "
    "already know from earlier in this conversation. "
    "(3) condition_id — same rule: only use one a retrieved passage's `condition_id=` "
    "field actually showed you, never a passage_id or an invented name."
)


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
        timeout: float = 60.0,
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
        system_content = f"{system_prompt}\n\n{_render_context(context)}{_JSON_SHAPE_INSTRUCTION}"
        messages = [
            {"role": "system", "content": system_content},
            *({"role": m.role, "content": m.content} for m in history),
        ]
        body = {
            "model": self._model,
            "messages": messages,
            "response_format": {"type": "json_object"},
            # Inconsistently honoured across OpenRouter's backing providers
            # (see _JSON_SHAPE_INSTRUCTION's comment) but harmless and cheap
            # to keep — when it is honoured, it skips a slow, unneeded
            # reasoning block for a turn that just needs to answer.
            "chat_template_kwargs": {"enable_thinking": False},
        }
        response = self._client.post(_OPENROUTER_URL, headers=self._headers, json=body)
        response.raise_for_status()
        try:
            payload = response.json()
            content = payload["choices"][0]["message"]["content"]
            return TriageDecision.model_validate(json.loads(content))
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
            raise ValueError(f"reasoning model returned malformed JSON: {error}") from error


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
