"""Provenance-quality policy for a CONCLUDE decision — ADR 0012 §3, rule 4.

Not called from anywhere inside :mod:`herhealth_backend.triage.agent` on
purpose — that module's docstring states plainly that the only code-level
judgement left in the agentic loop is ``max_turns``, and this is a real
judgement, not a dumb bound. It belongs to whoever *consumes* an
``AgentTurn``'s decision (the eventual API route — see ADR 0012's migration
checklist item 4, not started), applied once per turn before that decision
reaches a user.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from herhealth_contracts.decision import DecisionType, TriageDecision
from herhealth_contracts.knowledge import ActionCode, KnowledgeBase
from herhealth_contracts.retrieval import PassageType, RetrievedPassage

__all__ = ["drop_unknown_conditions", "enforce_provenance_cap"]

logger = logging.getLogger(__name__)


def drop_unknown_conditions(
    decision: TriageDecision, base: KnowledgeBase
) -> TriageDecision:
    """Remove named conditions that are not in ``conditions.yaml``, keeping the
    rest of the decision — above all its action code — intact.

    **Why drop rather than reject.** ``vocabulary.validate_against_knowledge_base``
    raises on an unknown condition id, and rightly so as a *check*; but the
    route turns that raise into a retry and then a 502, so a decision whose
    urgency was correct is thrown away over an optional field. Measured
    2026-09-11: the fine-tuned adapter answered EMERGENCY to sudden severe
    pelvic pain with faintness — the right call — and lost the whole turn to
    ``matching_conditions``. The base model did the same with
    ``poisoned_oil_poisoning``.

    ``matching_conditions`` is explicitly optional even on a qualifying
    CONCLUDE (see ``TriageDecision``): naming conditions is offered, not
    required. The action code is not optional and is the part that gets her
    to care. So the field that may legally be empty is the field that gives
    way.

    **What this does not do.** It never invents, substitutes or reorders a
    condition, and it never touches ``action_code`` or ``red_flag_id``. An
    invented ``red_flag_id`` is deliberately still a hard failure: it is
    load-bearing for the urgency itself, so silently dropping it would leave
    an escalation asserting a rule that does not exist.

    Every drop is logged. A model inventing condition names is a real defect
    and the fix for it is guided decoding, not this function — this only stops
    that defect costing a woman her answer in the meantime.
    """
    if not decision.matching_conditions:
        return decision

    known = base.conditions_by_id
    kept = tuple(c for c in decision.matching_conditions if c in known)
    dropped = [c for c in decision.matching_conditions if c not in known]
    if not dropped:
        return decision

    logger.warning(
        "dropped %d invented condition id(s) from a %s decision: %s",
        len(dropped),
        decision.action_code.value if decision.action_code else decision.type.value,
        ", ".join(sorted(dropped)),
    )
    return decision.model_copy(update={"matching_conditions": kept})


def enforce_provenance_cap(
    decision: TriageDecision, context: Sequence[RetrievedPassage]
) -> TriageDecision:
    """Floor a ``SELF_CARE`` conclusion at ``ROUTINE_APPOINTMENT`` when every
    citation behind it is a live, unreviewed fallback fetch rather than a
    reviewed passage. Nothing produces such a passage since the web fallback
    was removed with the retrieval service (ADR 0017); the floor stays as a
    guard should one ever be reintroduced.

    A red-flag-driven conclusion is untouched: it never carries citations by
    design (``red_flags.yaml`` is injected, never retrieved — see
    ``agent.render_red_flags``), so there is nothing here to check, and a
    fired red flag already implies an urgency the fallback path never
    produces on its own.

    ``TriageDecision`` is frozen, so this returns a new instance rather than
    mutating — ``decision`` itself is left alone, matching every other
    place in this codebase that treats a validated decision as immutable
    once emitted.
    """
    is_self_care_conclusion = (
        decision.type is DecisionType.CONCLUDE and decision.action_code is ActionCode.SELF_CARE
    )
    if not is_self_care_conclusion:
        return decision
    if decision.red_flag_id is not None:
        return decision

    by_id = {passage.id: passage for passage in context}
    cited = [by_id[citation_id] for citation_id in decision.citations if citation_id in by_id]
    if not cited:
        # Schema already requires a non-empty citations list when red_flag_id
        # is None; an empty match here means a citation pointed at a passage
        # this call was not given, not that there is nothing to check.
        return decision

    if all(passage.passage_type is PassageType.LIVE_FALLBACK for passage in cited):
        return decision.model_copy(update={"action_code": ActionCode.ROUTINE_APPOINTMENT})
    return decision
