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
from collections.abc import Sequence
from dataclasses import replace
from datetime import date, datetime
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from herhealth_contracts.decision import DecisionType, TriageDecision
from herhealth_contracts.retrieval import PassageType, RetrievedPassage
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from herhealth_backend.app.accounts.current_user import get_current_user
from herhealth_backend.app.accounts.models import User
from herhealth_backend.app.accounts.profile import health_note_for
from herhealth_backend.app.config import reasoning_timeout as configured_reasoning_timeout
from herhealth_backend.app.db import Database
from herhealth_backend.app.triage.models import ConsultationSession
from herhealth_backend.app.triage.models import Message as MessageRow
from herhealth_backend.app.triage.reasoning_models import (
    ReasoningModelOption,
    default_model_id,
)
from herhealth_backend.triage.age_bands import age_band_for
from herhealth_backend.triage.agent import Message, TriageAgent, render_known_background
from herhealth_backend.triage.provenance import enforce_provenance_cap
from herhealth_backend.triage.vocabulary import (
    ClosedVocabularyViolation,
    validate_against_knowledge_base,
)

__all__ = ["router"]

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/triage", tags=["triage"])

_USER_FACING_ERROR = "Something went wrong. Please try again."

#: Observed real latency ranged from a few seconds to ~90s across manual
#: testing (2026-09-01, OpenRouter routing this model across several
#: backing providers with visibly different speeds). Comfortably above
#: that, not a tight bound — see _run_turn's docstring for why this exists
#: at all (containment for an intermittent hang, not a normal request
#: budget).
REASONING_TIMEOUT_SECONDS = configured_reasoning_timeout()
#: OpenRouter occasionally returns schema-valid JSON with invented feature ids
#: or bad citations. One silent retry before surfacing 502 to the client —
#: observed live 2026-09-02: first attempt 502, identical second attempt 200.
MAX_REASONING_ATTEMPTS = 2


class TriageTurnRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: None starts a new consultation. Otherwise, one of hers to continue —
    #: see triage_turn's ownership check.
    session_id: uuid.UUID | None = None
    message: str = Field(min_length=1)
    #: Which reasoning model decides this turn — an id from
    #: ``GET /triage/models``. None means the default, which is always a
    #: reviewed model (see ``reasoning_models.default_model_id``): an
    #: unreviewed one has to be asked for, never arrived at by omission.
    #: Ignored entirely when the selector is off, so a crafted request
    #: cannot reach the adapter on a deployment that does not offer it.
    reasoning_model: str | None = None


class ReasoningModelSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    label: str
    description: str
    #: False means every answer from this model must carry a warning — see
    #: ``reasoning_models.ReasoningModelOption``.
    reviewed: bool
    is_default: bool


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


@router.get("/models", response_model=list[ReasoningModelSummary])
async def list_reasoning_models(
    http_request: Request,
    user: User = Depends(get_current_user),  # noqa: B008
) -> list[ReasoningModelSummary]:
    """The models this deployment lets a caller choose between.

    Empty when the selector is off, which is the default — the frontend then
    shows no control at all rather than a disabled one. Authenticated like
    every other triage route: which models a deployment runs is not
    something to hand to an anonymous caller.
    """
    options: dict[str, ReasoningModelOption] = getattr(
        http_request.app.state, "reasoning_models", {}
    )
    if not options:
        return []
    default_id = default_model_id(options)
    return [
        ReasoningModelSummary(
            id=option.id,
            label=option.label,
            description=option.description,
            reviewed=option.reviewed,
            is_default=option.id == default_id,
        )
        for option in options.values()
    ]


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
                "(set HERHEALTH_TRIAGE_MODE=demo for local testing, "
                "openrouter or vllm for real reasoning, "
                "or OPENROUTER_API_KEY for openrouter/vllm fallback)"
            ),
        )

    options: dict[str, ReasoningModelOption] = getattr(
        http_request.app.state, "reasoning_models", {}
    )
    chosen = _choose_reasoning_model(request.reasoning_model, options)
    if chosen is not None:
        # TriageAgent is a frozen dataclass, so swapping the reasoning
        # client means a new instance rather than mutating shared app state
        # — two concurrent turns on different models must not race over one
        # agent's field.
        agent = replace(agent, reasoning=chosen.client)

    database: Database = http_request.app.state.database
    try:
        return await _run_turn(request, user, agent, database, model=chosen)
    except SQLAlchemyError as error:
        logger.exception("database error in triage_turn")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="triage storage is unavailable — check database migrations",
        ) from error
    except (HTTPException, ValidationError, ClosedVocabularyViolation, httpx.HTTPError, ValueError):
        raise
    except Exception as error:
        logger.exception("unhandled exception in triage_turn")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_USER_FACING_ERROR,
        ) from error


async def _run_turn(
    request: TriageTurnRequest,
    user: User,
    agent: TriageAgent,
    database: Database,
    *,
    model: ReasoningModelOption | None = None,
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
    session_id, history, carried = await _load_session(request, user, database)
    history.append(Message(role="user", content=request.message))
    background = await _known_background(user, database)

    turn = None
    last_retryable_error: Exception | None = None
    for attempt in range(1, MAX_REASONING_ATTEMPTS + 1):
        try:
            loop = asyncio.get_running_loop()
            turn = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    functools.partial(
                        agent.run_turn,
                        history,
                        carried_context=carried,
                        background=background,
                    ),
                ),
                timeout=REASONING_TIMEOUT_SECONDS,
            )
            validate_against_knowledge_base(turn.decision, agent.base, turn.retrieved)
            break
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
        except httpx.HTTPError as error:
            logger.warning("triage dependency HTTP failure: %s", error)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="A service we rely on is temporarily unavailable. Please try again.",
            ) from error
        except (ValidationError, ClosedVocabularyViolation, ValueError) as error:
            last_retryable_error = error
            if attempt < MAX_REASONING_ATTEMPTS:
                logger.warning(
                    "reasoning attempt %s/%s failed (%s) — retrying",
                    attempt,
                    MAX_REASONING_ATTEMPTS,
                    error,
                )
                continue
            if isinstance(error, ValidationError):
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="We had trouble understanding the response. Please try again.",
                ) from error
            if isinstance(error, ClosedVocabularyViolation):
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"reasoning model returned an invalid decision: {error}",
                ) from error
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=str(error),
            ) from error

    if turn is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"reasoning model failed after {MAX_REASONING_ATTEMPTS} attempts: "
            f"{last_retryable_error}",
        )

    decision = enforce_provenance_cap(turn.decision, turn.retrieved)
    payload = _decision_payload(decision, turn.retrieved, model=model)
    await _persist_turn(session_id, request.message, decision, payload, database)

    return {"session_id": str(session_id), "decision": payload}


def _decision_payload(
    decision: TriageDecision,
    retrieved: Sequence[RetrievedPassage],
    *,
    model: ReasoningModelOption | None = None,
) -> dict[str, Any]:
    """``TriageDecision`` as JSON, plus the passages its ``citations`` name.

    ``citations`` on its own is a list of 16-hex-character content hashes —
    meaningful to :func:`validate_against_knowledge_base`, meaningless to a
    person. Resolving them here, against the very passages this turn
    retrieved, is what lets the UI show the sentence a conclusion actually
    rests on and a link to the page it came from, rather than a hash or a
    vague "grounded in 3 sources".

    Resolved eagerly rather than looked up later on purpose: retrieval is a
    live similarity search, so the same citation id is not guaranteed to
    come back from a future search. The passages are captured with the turn
    or not at all.

    The extra key rides alongside ``TriageDecision``'s own fields rather
    than inside them — the model is ``extra="forbid"``, and it should stay
    that way: what the reasoning model may emit and what this API renders
    are different contracts, and only the first one is the safety net.
    """
    by_id = {passage.id: passage for passage in retrieved}
    cited = [by_id[citation] for citation in decision.citations if citation in by_id]
    payload: dict[str, Any] = {
        **decision.model_dump(mode="json"),
        "cited_passages": [
            {
                "id": passage.id,
                "text": passage.text,
                "citation": passage.citation,
                "source_id": passage.source_id,
                "url": passage.url,
                "passage_type": passage.passage_type.value,
            }
            for passage in cited
        ],
    }
    if model is not None:
        # Stored with the turn, not just returned: reopening an old
        # consultation has to show which model produced it, or an answer
        # from the unreviewed adapter becomes indistinguishable from a
        # reviewed one the moment the page is reloaded.
        payload["reasoning_model"] = {
            "id": model.id,
            "label": model.label,
            "reviewed": model.reviewed,
        }
    return payload


def _choose_reasoning_model(
    requested: str | None, options: dict[str, ReasoningModelOption]
) -> ReasoningModelOption | None:
    """Resolve a requested model id, or ``None`` to leave the agent as built.

    Returns ``None`` when the selector is off, whatever was asked for: a
    deployment that offers no choice must not be steerable by a request
    body, which is what makes ``HERHEALTH_MODEL_SELECTOR`` an actual gate
    rather than a UI preference.

    An unknown id is a 400 rather than a silent fall back to the default.
    Silently substituting would mean an answer labelled as coming from one
    model was produced by another, and the label is the whole safety
    mechanism for an unreviewed model.
    """
    if not options:
        return None
    if requested is None:
        return options[default_model_id(options)]
    option = options.get(requested)
    if option is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"unknown reasoning model {requested!r}; see GET /triage/models",
        )
    return option


async def _known_background(user: User, database: Database) -> str | None:
    """Her stored age band and health note, rendered for the system prompt.

    This is the one place the Accounts and Triage contexts meet over her
    profile, which ``CONTEXT-MAP.md`` permits only at the API layer — hence
    it living here and not inside ``TriageAgent``.

    The band is derived from her date of birth on every turn rather than
    read from a column, so a consultation that runs on her birthday uses the
    band she is in today. See ``triage.age_bands``.
    """
    age_band = (
        age_band_for(user.date_of_birth, today=date.today())
        if user.date_of_birth is not None
        else None
    )
    async with database.session() as session:
        note = await health_note_for(session, user.id)
    return render_known_background(
        age_band=age_band,
        health_note=note.content if note is not None else None,
    )


def _passage_from_cited(raw: object) -> RetrievedPassage | None:
    """Rebuild a passage from a stored ``cited_passages`` row.

    Score is not persisted (the UI does not show it). Carried passages exist
    so a later turn can still cite them — see ``TriageAgent.run_turn`` —
    so a dummy 0.0 is enough; they are not re-ranked.
    """
    if not isinstance(raw, dict):
        return None
    try:
        return RetrievedPassage(
            id=raw["id"],
            passage_type=PassageType(raw["passage_type"]),
            source_id=raw["source_id"],
            text=raw["text"],
            citation=raw["citation"],
            score=0.0,
            url=raw.get("url"),
        )
    except (KeyError, TypeError, ValidationError):
        return None


async def _load_session(
    request: TriageTurnRequest, user: User, database: Database
) -> tuple[uuid.UUID, list[Message], tuple[RetrievedPassage, ...]]:
    """A short-lived session: create or look up the consultation, load its
    prior messages, and return plain data — nothing SQLAlchemy-attached
    survives past this function, so nothing here can be lazy-loaded later
    outside its session's greenlet.

    The third value is every passage this consultation has already cited,
    rebuilt from stored assistant decisions. Without it, turn two of a
    live session 502s when the model re-cites turn-one evidence that this
    turn's retrieval did not return — see ``build_retrieval_query``.
    """
    async with database.session() as session:
        consultation: ConsultationSession | None
        if request.session_id is None:
            consultation = ConsultationSession(user_id=user.id)
            session.add(consultation)
            await session.commit()
            return consultation.id, [], ()

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
        history: list[Message] = []
        carried_by_id: dict[str, RetrievedPassage] = {}
        for row in rows:
            history.append(Message(role=row.role, content=row.content))
            if row.role != "assistant" or not isinstance(row.decision, dict):
                continue
            for raw in row.decision.get("cited_passages") or []:
                passage = _passage_from_cited(raw)
                if passage is not None:
                    carried_by_id.setdefault(passage.id, passage)
        return consultation.id, history, tuple(carried_by_id.values())


async def _persist_turn(
    session_id: uuid.UUID,
    user_message: str,
    decision: TriageDecision,
    payload: dict[str, Any],
    database: Database,
) -> None:
    """A second short-lived session: write this turn's two messages, and
    close out the consultation if it concluded.

    Stores ``payload`` — the decision *with* its resolved
    ``cited_passages`` (see :func:`_decision_payload`) — not the bare
    decision. Reopening an old consultation from the sidebar therefore
    shows the same quoted sources it showed live, without re-running a
    retrieval that might not return the same passages today.
    """
    # A decline shares CONCLUDE's branch here — its rationale is the refusal
    # she reads (see decision.py) — but deliberately not the status change
    # below: an off-scope message must not burn her consultation, so the
    # session stays active and she can ask something in scope next.
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
                decision=payload,
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
    except HTTPException:
        raise
    except Exception as error:
        logger.exception("unexpected error in list_sessions")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_USER_FACING_ERROR,
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
    except Exception as error:
        logger.exception("unexpected error in get_session")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_USER_FACING_ERROR,
        ) from error


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: uuid.UUID,
    http_request: Request,
    user: User = Depends(get_current_user),  # noqa: B008
) -> None:
    """Permanently remove one consultation and its messages.

    Messages cascade via the FK on ``messages.session_id``. Same ownership
    discipline as ``get_session``: not-found, never a 403.
    """
    database: Database = http_request.app.state.database
    try:
        async with database.session() as session:
            consultation = await session.get(ConsultationSession, session_id)
            if consultation is None or consultation.user_id != user.id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no such session")
            await session.delete(consultation)
            await session.commit()
    except HTTPException:
        raise
    except SQLAlchemyError as error:
        logger.exception("database error in delete_session")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="triage storage is unavailable — check database migrations",
        ) from error
    except Exception as error:
        logger.exception("unexpected error in delete_session")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_USER_FACING_ERROR,
        ) from error
