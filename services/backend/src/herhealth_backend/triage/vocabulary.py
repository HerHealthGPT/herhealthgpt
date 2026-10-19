"""Closed-vocabulary validation for a reasoning-model decision.

``TriageDecision``'s own schema validates *shape* (an id is lowercase
snake_case, ``matching_conditions`` has at most 5 items) but cannot validate
*content* against the real knowledge base or what was actually retrieved
this turn — it has no access to either at validation time (see
``herhealth_contracts.decision``). This is that second check. Like
``provenance.enforce_provenance_cap``, it is not called from anywhere inside
``herhealth_backend.triage.agent`` on purpose — that module's docstring
states the only code-level judgement left in the agentic loop is
``max_turns``. It belongs to whoever consumes an ``AgentTurn``.

Found necessary empirically, not speculatively: a live test against
``OpenRouterReasoningClient`` (2026-09-01, base model, no fine-tuned
adapter) returned ``next_feature_id="period_pain_and_patterns_001"`` —
format-valid, schema-valid, and not a real id anywhere in ``features.yaml``.
True guided decoding (a self-hosted vLLM server enforcing the schema's
enums directly) would make this structurally impossible; OpenRouter's
plain-JSON mode (see ``clients.py``) cannot provide that guarantee, so this
exists to catch it after the fact instead.
"""

from __future__ import annotations

import difflib
from collections.abc import Sequence

from herhealth_contracts.decision import DecisionType, TriageDecision
from herhealth_contracts.knowledge import UNKNOWN_VALUE, KnowledgeBase
from herhealth_contracts.retrieval import RetrievedPassage

__all__ = ["ClosedVocabularyViolation", "validate_against_knowledge_base"]


class ClosedVocabularyViolation(ValueError):
    """A decision referenced a feature, condition, red flag or citation that
    does not exist. Raised rather than silently rewritten — unlike
    ``provenance.enforce_provenance_cap``'s ``SELF_CARE`` floor, there is no
    safe substitute for "asks about a feature that isn't real": the caller
    must re-prompt, ask something else, or fail the turn, not guess at what
    was meant.
    """


def closest_features(base: KnowledgeBase, invented: str, count: int = 3) -> list[str]:
    """The real feature ids nearest an invented one, by id and label.

    Measured 2026-10-19: the model builds ids from a feature's label, so
    ``difficulty_becoming_pregnant`` for ``difficulty_conceiving`` (label
    "Difficulty becoming pregnant"). Told only to use a real id, it made the
    same guess on the retry. A suggestion, never a substitution: the model
    still chooses (see :class:`ClosedVocabularyViolation`).
    """
    wanted = invented.replace("_", " ")

    def score(feature_id: str) -> float:
        label = base.features_by_id[feature_id].label.lower()
        return max(
            difflib.SequenceMatcher(None, wanted, feature_id.replace("_", " ")).ratio(),
            difflib.SequenceMatcher(None, wanted, label).ratio(),
        )

    return sorted(base.features_by_id, key=score, reverse=True)[:count]


def _did_you_mean(base: KnowledgeBase, invented: str) -> str:
    return "; the closest real ids are " + ", ".join(closest_features(base, invented))


def validate_against_knowledge_base(
    decision: TriageDecision, base: KnowledgeBase, context: Sequence[RetrievedPassage]
) -> None:
    """Raise :class:`ClosedVocabularyViolation` if ``decision`` references
    anything that is not real, checked against its actual source of truth:
    ``features.yaml``, ``conditions.yaml``, ``red_flags.yaml``, or the
    passages retrieved this specific turn. Returns normally (no return
    value) when everything checks out.
    """
    if decision.type is DecisionType.ASK and decision.next_feature_id not in base.features_by_id:
        raise ClosedVocabularyViolation(
            f"next_feature_id {decision.next_feature_id!r} is not a real feature in features.yaml"
            + _did_you_mean(base, decision.next_feature_id or "")
        )

    for condition_id in decision.matching_conditions:
        if condition_id not in base.conditions_by_id:
            raise ClosedVocabularyViolation(
                f"matching_conditions references {condition_id!r}, "
                "not a real condition in conditions.yaml"
            )

    if decision.red_flag_id is not None:
        real_red_flag_ids = {rule.id for rule in base.red_flags}
        if decision.red_flag_id not in real_red_flag_ids:
            raise ClosedVocabularyViolation(
                f"red_flag_id {decision.red_flag_id!r} is not a real rule in red_flags.yaml"
            )

    for feature_id, value in decision.observed.items():
        feature = base.features_by_id.get(feature_id)
        if feature is None:
            raise ClosedVocabularyViolation(
                f"observed references {feature_id!r}, not a real feature in features.yaml"
                + _did_you_mean(base, feature_id)
            )
        # ``unknown`` is always legal and is not in any feature's
        # ``allowed_values``: "she was asked and could not say" has to be
        # recordable, or the feature would look unasked forever and the
        # escalation screen would keep probing it. A feature with no authored
        # ``allowed_values`` is free text and is not checked.
        if (
            feature.allowed_values
            and value != UNKNOWN_VALUE
            and value not in feature.allowed_values
        ):
            allowed = ", ".join(feature.allowed_values)
            raise ClosedVocabularyViolation(
                f"observed[{feature_id!r}] = {value!r} is not one of that "
                f"feature's allowed_values ({allowed}) — an answer outside "
                "the value vocabulary cannot be matched against a red-flag "
                "clause or joined to an evidence row, so it is silently "
                "inert rather than merely untidy"
            )

    retrieved_ids = {passage.id for passage in context}
    for citation in decision.citations:
        if citation not in retrieved_ids:
            raise ClosedVocabularyViolation(
                f"citation {citation!r} was not among the passages retrieved this turn"
            )
