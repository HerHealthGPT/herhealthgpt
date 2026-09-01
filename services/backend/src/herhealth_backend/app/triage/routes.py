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

import asyncio
import functools
import logging
import uuid
from datetime import datetime
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from herhealth_contracts.decision import DecisionType, TriageDecision
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/triage", tags=["triage"])

#: Observed real latency ranged from a few seconds to ~90s across manual
#: testing (2026-09-01, OpenRouter routing this model across several
#: backing providers with visibly different speeds). Comfortably above
#: that, not a tight bound — see _run_turn's docstring for why this exists
#: at all (containment for an intermittent hang, not a normal request
#: budget).
REASONING_TIMEOUT_SECONDS = 150.0


class TriageTurnRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: None starts a new consultation. Otherwise, one of hers to continue —
    #: see triage_turn's ownership check.
    session_id: uuid.UUID | None = None
    message: str = Field(min_length=1)


class SessionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    status: str
    created_at: datetime
    preview: str


class SessionMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    role: str
    content: str
    decision: dict[str, Any] | None = None
    created_at: datetime


class SessionDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    status: str
    created_at: datetime
    messages: list[SessionMessage]


@router.post("/turn")
async def triage_turn(
    request: TriageTurnRequest,
    http_request: Request,
    user: User = Depends(get_current_user),  # noqa: B008
) -> dict[str, Any]:
    """Load (or start) a session, run one turn, persist it, return it.

    The reasoning/retrieval calls inside ``agent.run_turn`` are blocking
    (``httpx.Client``, not ``AsyncClient`` — see ``triage/clients.py``), so
    this route is ``async def`` for its database access but routes that one
    call through a plain ``loop.run_in_executor`` (see ``_run_turn``) rather
    than blocking the event loop for however long OpenRouter or
    ``services/model`` takes to answer — the same reasoning
    ``app/main.py``'s ``_build_email_sender`` documents for its own blocking
    call inside an async context.
    """
    agent: TriageAgent | None = getattr(http_request.app.state, "triage_agent", None)
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "triage is not configured on this deployment "
                "(set HERHEALTH_TRIAGE_MODE=demo for local testing, or OPENROUTER_API_KEY for real)"
            ),
        )

    database: Database = http_request.app.state.database
    try:
        return await _run_turn(request, user, agent, database)
    except SQLAlchemyError as error:
        logger.exception("database error in triage_turn")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="triage storage is unavailable — check database migrations",
        ) from error
    except (HTTPException, ValidationError, ClosedVocabularyViolation, httpx.HTTPError, ValueError):
        raise
    except Exception:
        # Belt and braces: an unhandled exception here would otherwise
        # surface only as Starlette's bare "Internal Server Error" with
        # nothing in this process's own log to explain it — exactly what
        # happened while diagnosing the session-held-open bug _run_turn's
        # docstring describes. Re-raised unchanged; this only adds a log line.
        logger.exception("unhandled exception in triage_turn")
        raise


async def _run_turn(
    request: TriageTurnRequest, user: User, agent: TriageAgent, database: Database
) -> dict[str, Any]:
    """Three short phases: read, the slow blocking call, then write — not
    one open database session spanning all of them (see the note on that
    below).

    ``run_in_executor`` here, not ``anyio.to_thread.run_sync``: with the
    latter, a request that reached both the retrieval and reasoning calls
    (both logged success) then simply vanished — no response, no exception
    anywhere in this process's own log, no uvicorn request-completion line.
    Switching to the stdlib primitive reduced how often this happens but did
    **not** eliminate it — the same silent-hang symptom still recurs
    intermittently (confirmed live, 2026-09-01: two consecutive identical
    requests, one completed normally, the next hung the same way). The root
    cause is still open — a leading theory is thread-safety of the single,
    long-lived ``httpx.Client`` each of ``OpenRouterReasoningClient`` and
    ``HttpRetrievalClient`` holds, reused across concurrent requests'
    executor threads, but this is not yet confirmed. ``asyncio.wait_for``
    below is a deliberate containment measure, not a fix: whatever is
    hanging still hangs, but the request now fails cleanly and promptly
    instead of hanging forever.

    Not holding the database session open across this call is worth keeping
    regardless of the above: a multi-second-to-multi-minute idle transaction
    during an unrelated external HTTP call is wasteful on its own terms.
    """
    session_id, history = await _load_session(request, user, database)
    history.append(Message(role="user", content=request.message))

    try:
        loop = asyncio.get_running_loop()
        turn = await asyncio.wait_for(
            loop.run_in_executor(
                None, functools.partial(agent.run_turn, history, query=history[-1].content)
            ),
            timeout=REASONING_TIMEOUT_SECONDS,
        )
        validate_against_knowledge_base(turn.decision, agent.base, turn.retrieved)
    except TimeoutError as error:
        # Containment for the still-unexplained intermittent hang this
        # function's docstring describes — not a fix for it. The stuck
        # executor thread is not cancelled (Python threads cannot be
        # forced to stop) and is abandoned; it will not be returned to the
        # executor's pool. A deployment that hits this repeatedly is
        # leaking worker threads until the process is restarted — a real,
        # named cost of containing rather than fixing this.
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="the reasoning model did not respond in time",
        ) from error
    except ValidationError as error:
        # Raised inside OpenRouterReasoningClient.decide() (clients.py) when
        # the model's JSON is syntactically valid but violates
        # TriageDecision's own schema — e.g. putting a retrieved-passage hash
        # where a real feature/condition id belongs, observed live in testing
        # (2026-09-01). Upstream's fault, never a bare 500.
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
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(error),
        ) from error

    decision = enforce_provenance_cap(turn.decision, turn.retrieved)
    await _persist_turn(session_id, request.message, decision, database)

    return {"session_id": str(session_id), "decision": decision.model_dump(mode="json")}


async def _load_session(
    request: TriageTurnRequest, user: User, database: Database
) -> tuple[uuid.UUID, list[Message]]:
    """A short-lived session: create or look up the consultation, load its
    prior messages, and return plain data — nothing SQLAlchemy-attached
    survives past this function, so nothing here can be lazy-loaded later
    outside its session's greenlet.
    """
    async with database.session() as session:
        consultation: ConsultationSession | None
        if request.session_id is None:
            consultation = ConsultationSession(user_id=user.id)
            session.add(consultation)
            await session.commit()
            return consultation.id, []

        consultation = await session.get(ConsultationSession, request.session_id)
        if consultation is None or consultation.user_id != user.id:
            # Same discipline issue #13 establishes for its own
            # conversations: not-found, never a 403 that would confirm a
            # session with this id exists and just isn't hers.
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no such session")
        if consultation.status == "concluded":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="this consultation has already concluded",
            )

        rows = await session.scalars(
            select(MessageRow)
            .where(MessageRow.session_id == consultation.id)
            .order_by(MessageRow.created_at)
        )
        history = [Message(role=row.role, content=row.content) for row in rows]
        return consultation.id, history


async def _persist_turn(
    session_id: uuid.UUID, user_message: str, decision: TriageDecision, database: Database
) -> None:
    """A second short-lived session: write this turn's two messages, and
    close out the consultation if it concluded."""
    assistant_content = (
        decision.question_text if decision.type is DecisionType.ASK else decision.rationale
    )
    async with database.session() as session:
        session.add(MessageRow(session_id=session_id, role="user", content=user_message))
        session.add(
            MessageRow(
                session_id=session_id,
                role="assistant",
                content=assistant_content,
                decision=decision.model_dump(mode="json"),
            )
        )
        if decision.type is DecisionType.CONCLUDE:
            consultation = await session.get(ConsultationSession, session_id)
            assert consultation is not None  # loaded or created moments ago, in _load_session
            consultation.status = "concluded"
        await session.commit()


_PREVIEW_MAX_LEN = 80
_DEFAULT_PREVIEW = "New conversation"


def _preview_from_content(content: str) -> str:
    text = content.strip()
    if not text:
        return _DEFAULT_PREVIEW
    if len(text) <= _PREVIEW_MAX_LEN:
        return text
    return f"{text[: _PREVIEW_MAX_LEN - 1].rstrip()}…"


@router.get("/sessions")
async def list_sessions(
    http_request: Request,
    user: User = Depends(get_current_user),  # noqa: B008
) -> list[SessionSummary]:
    """List this user's consultations, newest first."""
    database: Database = http_request.app.state.database
    try:
        async with database.session() as session:
            consultations = (
                await session.scalars(
                    select(ConsultationSession)
                    .where(ConsultationSession.user_id == user.id)
                    .order_by(ConsultationSession.created_at.desc())
                )
            ).all()
            if not consultations:
                return []

            session_ids = [consultation.id for consultation in consultations]
            first_user_messages = (
                await session.scalars(
                    select(MessageRow)
                    .where(
                        MessageRow.session_id.in_(session_ids),
                        MessageRow.role == "user",
                    )
                    .order_by(MessageRow.session_id, MessageRow.created_at)
                    .distinct(MessageRow.session_id)
                )
            ).all()
            previews = {
                row.session_id: _preview_from_content(row.content) for row in first_user_messages
            }

            return [
                SessionSummary(
                    id=consultation.id,
                    status=consultation.status,
                    created_at=consultation.created_at,
                    preview=previews.get(consultation.id, _DEFAULT_PREVIEW),
                )
                for consultation in consultations
            ]
    except SQLAlchemyError as error:
        logger.exception("database error in list_sessions")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="triage storage is unavailable — check database migrations",
        ) from error


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: uuid.UUID,
    http_request: Request,
    user: User = Depends(get_current_user),  # noqa: B008
) -> SessionDetail:
    """Return one consultation's full transcript for the chat UI."""
    database: Database = http_request.app.state.database
    try:
        async with database.session() as session:
            consultation = await session.get(ConsultationSession, session_id)
            if consultation is None or consultation.user_id != user.id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no such session")

            rows = (
                await session.scalars(
                    select(MessageRow)
                    .where(MessageRow.session_id == consultation.id)
                    .order_by(MessageRow.created_at)
                )
            ).all()

            return SessionDetail(
                id=consultation.id,
                status=consultation.status,
                created_at=consultation.created_at,
                messages=[
                    SessionMessage(
                        id=row.id,
                        role=row.role,
                        content=row.content,
                        decision=row.decision,
                        created_at=row.created_at,
                    )
                    for row in rows
                ],
            )
    except HTTPException:
        raise
    except SQLAlchemyError as error:
        logger.exception("database error in get_session")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="triage storage is unavailable — check database migrations",
        ) from error
