"""HTTP surface for the agentic triage loop — ADR 0012, issue #20 item 7.

One route, one turn per request. The client owns and resends the growing
message history — there is no session/message persistence yet (issue #20
item 6, a separate piece of work; #13's Accounts-context "conversation"
storage is downstream of that again, and explicitly may not touch this
context — see CONTEXT-MAP.md).

Kept a thin translation layer, the same discipline
``app/accounts/routes.py`` states for itself: the actual loop lives in
``herhealth_backend.triage.agent.TriageAgent``, this module only moves HTTP
in and out of it.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict

from herhealth_backend.app.accounts.current_user import get_current_user
from herhealth_backend.app.accounts.models import User
from herhealth_backend.triage.agent import Message, TriageAgent
from herhealth_backend.triage.provenance import enforce_provenance_cap
from herhealth_backend.triage.vocabulary import (
    ClosedVocabularyViolation,
    validate_against_knowledge_base,
)

__all__ = ["router"]

router = APIRouter(prefix="/triage", tags=["triage"])


class TurnMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str
    content: str


class TriageTurnRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: The whole conversation so far, ending in her latest message. The
    #: server holds none of this between requests — see the module
    #: docstring for why that is a scope decision, not an oversight.
    history: list[TurnMessage]


@router.post("/turn")
def triage_turn(
    request: TriageTurnRequest,
    http_request: Request,
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """One retrieve-then-reason turn.

    Deliberately not ``async def``: ``TriageAgent``'s reasoning and
    retrieval clients make blocking HTTP calls (``httpx.Client``, not
    ``AsyncClient``) — see ``triage/clients.py``. FastAPI runs a sync route
    function in its own threadpool rather than on the event loop, which is
    what keeps this from blocking every other request while OpenRouter or
    ``services/model`` responds; ``app/main.py``'s ``_build_email_sender``
    needed ``to_thread.run_sync`` for the same reason because it is called
    from *inside* an ``async def`` lifespan, not a route FastAPI dispatches
    itself.
    """
    agent: TriageAgent | None = getattr(http_request.app.state, "triage_agent", None)
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="triage is not configured on this deployment (OPENROUTER_API_KEY unset)",
        )
    if not request.history or request.history[-1].role != "user":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="history must be non-empty and end with a user message",
        )

    messages = [Message(role=m.role, content=m.content) for m in request.history]
    turn = agent.run_turn(messages, query=messages[-1].content)

    try:
        validate_against_knowledge_base(turn.decision, agent.base, turn.retrieved)
    except ClosedVocabularyViolation as error:
        # The reasoning model's fault, not the caller's request — see
        # vocabulary.py's docstring for why this is checked here rather than
        # prevented structurally. 502: this route is itself a gateway to an
        # upstream model that returned something invalid.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"reasoning model returned an invalid decision: {error}",
        ) from error

    decision = enforce_provenance_cap(turn.decision, turn.retrieved)
    return decision.model_dump(mode="json")
