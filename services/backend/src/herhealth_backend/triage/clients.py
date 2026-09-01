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
    unconditionally, this is injected only when retrieval found something."""
    if not context:
        return "No retrieved passages matched this turn."
    lines = ["Retrieved passages — cite one by its id in `citations` if you use it:"]
    lines.extend(f'- [{p.id}] ({p.citation}): "{p.text}"' for p in context)
    return "\n".join(lines)


class OpenRouterReasoningClient:
    """Implements ``herhealth_backend.triage.agent.ReasoningClient`` against
    OpenRouter's chat-completions API, requesting structured output
    constrained to ``TriageDecision.model_json_schema()`` — the same
    guided-decoding contract ADR 0011 specifies, enforced by a different
    server than the self-hosted vLLM it originally described (ADR 0012).

    Whether OpenRouter's various backing providers honour ``strict`` mode
    against the *full* schema Pydantic generates (nested ``$defs``, tuple
    ``max_length`` constraints, ``StrEnum`` members) is not yet verified
    empirically — only that OpenRouter advertises structured-output support
    for this model in general. :meth:`decide` re-validates with Pydantic on
    receipt regardless, so a provider that only partially enforces the
    schema fails here, legibly, rather than deeper inside ``TriageAgent``.
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
        messages = [
            {"role": "system", "content": f"{system_prompt}\n\n{_render_context(context)}"},
            *({"role": m.role, "content": m.content} for m in history),
        ]
        body = {
            "model": self._model,
            "messages": messages,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "TriageDecision",
                    "strict": True,
                    "schema": TriageDecision.model_json_schema(),
                },
            },
        }
        response = self._client.post(_OPENROUTER_URL, headers=self._headers, json=body)
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return TriageDecision.model_validate(json.loads(content))


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
