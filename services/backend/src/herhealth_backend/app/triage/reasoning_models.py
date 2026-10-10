"""Which reasoning models a caller may pick from, and what each one is.

One place that answers "what can decide a turn here", so ``GET
/triage/models`` and the per-turn routing in ``routes.py`` cannot disagree
about it. See ADR 0016.

**Why ``reviewed`` is a field and not a comment.** The fine-tuned adapter is
not cleared to make triage decisions: it was trained on
``gold_seeds_styled.csv``, which contains no example where the correct answer
is a clarifying question, and CLAUDE.md records what that produced —
clarification-seeking collapsing from 0.856 to 0.000 and French/Arabic
under-triage reaching 0.994.
``docs/runbooks/dev-vllm-lora-endpoint.md`` §6 states the restriction as a
hard constraint. Offering it in a selector at all is a deliberate,
scoped exception for measurement (ADR 0016), so the flag rides with the
model, reaches the API response, and is rendered as a warning on every
answer it produces. A reader of this module cannot miss which is which.
"""

from __future__ import annotations

from dataclasses import dataclass

from herhealth_backend.triage.agent import ReasoningClient

__all__ = [
    "BASE_MODEL_ID",
    "FINE_TUNED_MODEL_ID",
    "ReasoningModelOption",
    "default_model_id",
]

#: The unadapted base model, served through OpenRouter (ADR 0012).
BASE_MODEL_ID = "base"

#: Base + this project's QLoRA adapter, served by a self-hosted vLLM.
FINE_TUNED_MODEL_ID = "fine-tuned"


@dataclass(frozen=True, slots=True)
class ReasoningModelOption:
    """One selectable model, and the client that reaches it."""

    id: str
    label: str
    #: One sentence a non-engineer can read, shown under the option.
    description: str
    #: False means: this model's decisions are not cleared for use as
    #: guidance, and every answer it produces must be labelled. Never
    #: default to True for a new option — say why it is trusted first.
    reviewed: bool
    client: ReasoningClient


def default_model_id(options: dict[str, ReasoningModelOption]) -> str:
    """The model used when a caller names none.

    Always a reviewed one when any exists, regardless of what else is
    configured — an unreviewed model must be chosen explicitly, never
    arrived at by leaving a field blank. Falls back to the first option only
    when nothing is reviewed, which is a deployment that has deliberately
    configured only the adapter.
    """
    for option in options.values():
        if option.reviewed:
            return option.id
    return next(iter(options))
