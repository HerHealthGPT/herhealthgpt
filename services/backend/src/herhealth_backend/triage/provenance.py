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

from collections.abc import Sequence

from herhealth_contracts.decision import DecisionType, TriageDecision
from herhealth_contracts.knowledge import ActionCode
from herhealth_contracts.retrieval import PassageType, RetrievedPassage

__all__ = ["enforce_provenance_cap"]


def enforce_provenance_cap(
    decision: TriageDecision, context: Sequence[RetrievedPassage]
) -> TriageDecision:
    """Floor a ``SELF_CARE`` conclusion at ``ROUTINE_APPOINTMENT`` when every
    citation behind it is a live, unreviewed fallback fetch (see
    ``herhealth_model.web_fallback``) rather than a reviewed passage.

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
