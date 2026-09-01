"""HTTP surface for the agentic triage loop — ADR 0012, issue #20 items 6-7.

One route, one turn per request. The server now owns the growing
transcript (issue #20 item 6): the caller sends only her newest message
plus the session id (``null`` to start a new one), not the whole history —
see ``app/triage/models.py`` for the two tables this persists to. The full
verbatim transcript is replayed to the reasoning model every turn,
deliberately not summarised — a dropped detail could suppress a red flag,
and this project's standing rule is to fail toward escalating, not away
from it.

Kept a thin translation layer, the same discipline
``app/accounts/routes.py`` states for itself: the actual loop lives in
``herhealth_backend.triage.agent.TriageAgent``, this module only moves HTTP
(and now persistence) around it.
"""

from __future__ import annotations

import functools
import uuid
from typing import Any

import httpx
from anyio import to_thread
from fastapi import APIRouter, Depends, HTTPException, Request, status
from herhealth_contracts.decision import DecisionType
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select

from herhealth_backend.app.accounts.current_user import get_current_user
from herhealth_backend.app.accounts.models import User
from herhealth_backend.app.db import Database
from herhealth_backend.app.triage.models import ConsultationSession
from herhealth_backend.app.triage.models import Message as MessageRow
from herhealth_backend.triage.agent import Message, TriageAgent
from herhealth_backend.triage.provenance import enforce_provenance_cap
from herhealth_backend.triage.vocabulary import (
    ClosedVocabularyViolation,
    validate_against_knowledge_base,
)

__all__ = ["router"]

router = APIRouter(prefix="/triage", tags=["triage"])


class TriageTurnRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: None starts a new consultation. Otherwise, one of hers to continue —
    #: see triage_turn's ownership check.
    session_id: uuid.UUID | None = None
    message: str = Field(min_length=1)


@router.post("/turn")
async def triage_turn(
    request: TriageTurnRequest,
    http_request: Request,
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Load (or start) a session, run one turn, persist it, return it.

    The reasoning/retrieval calls inside ``agent.run_turn`` are blocking
    (``httpx.Client``, not ``AsyncClient`` — see ``triage/clients.py``), so
    this route is ``async def`` for its database access but routes that one
    call through ``anyio.to_thread.run_sync`` rather than blocking the event
    loop for however long OpenRouter or ``services/model`` takes to answer —
    the same reasoning ``app/main.py``'s ``_build_email_sender`` documents
    for its own blocking call inside an async context.
    """
    agent: TriageAgent | None = getattr(http_request.app.state, "triage_agent", None)
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="triage is not configured on this deployment (OPENROUTER_API_KEY unset)",
        )

    database: Database = http_request.app.state.database
    async with database.session() as session:
        if request.session_id is None:
            consultation = ConsultationSession(user_id=user.id)
            session.add(consultation)
            await session.flush()
            history: list[Message] = []
        else:
            consultation = await session.get(ConsultationSession, request.session_id)
            if consultation is None or consultation.user_id != user.id:
                # Same discipline issue #13 establishes for its own
                # conversations: not-found, never a 403 that would confirm
                # a session with this id exists and just isn't hers.
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no such session")
            if consultation.status == "concluded":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="this consultation has already concluded",
                )
            # Not consultation.messages: that relationship lazy-loads, and a
            # lazy load outside SQLAlchemy's async greenlet raises
            # MissingGreenlet rather than a useful error — the same class of
            # trap conftest.py's db_session fixture documents for a
            # different attribute. An explicit, ordered query sidesteps it.
            rows = await session.scalars(
                select(MessageRow)
                .where(MessageRow.session_id == consultation.id)
                .order_by(MessageRow.created_at)
            )
            history = [Message(role=row.role, content=row.content) for row in rows]

        history.append(Message(role="user", content=request.message))

        try:
            turn = await to_thread.run_sync(
                functools.partial(agent.run_turn, history, query=history[-1].content)
            )
            validate_against_knowledge_base(turn.decision, agent.base, turn.retrieved)
        except ValidationError as error:
            # Raised inside OpenRouterReasoningClient.decide() (clients.py)
            # when the model's JSON is syntactically valid but violates
            # TriageDecision's own schema — e.g. putting a retrieved-passage
            # hash where a real feature/condition id belongs, observed live
            # in testing (2026-09-01). Upstream's fault, never a bare 500.
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"reasoning model returned a decision that failed schema validation: {error}",
            ) from error
        except ClosedVocabularyViolation as error:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"reasoning model returned an invalid decision: {error}",
            ) from error
        except httpx.HTTPError as error:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"a dependency of triage (OpenRouter or services/model) failed: {error}",
            ) from error

        decision = enforce_provenance_cap(turn.decision, turn.retrieved)
        assistant_content = (
            decision.question_text if decision.type is DecisionType.ASK else decision.rationale
        )

        session.add(MessageRow(session_id=consultation.id, role="user", content=request.message))
        session.add(
            MessageRow(
                session_id=consultation.id,
                role="assistant",
                content=assistant_content,
                decision=decision.model_dump(mode="json"),
            )
        )
        if decision.type is DecisionType.CONCLUDE:
            consultation.status = "concluded"

        await session.commit()
        session_id = consultation.id

    return {"session_id": str(session_id), "decision": decision.model_dump(mode="json")}
