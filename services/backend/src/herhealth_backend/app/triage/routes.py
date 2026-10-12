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
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from herhealth_contracts.decision import DecisionType, TriageDecision
from herhealth_contracts.knowledge import KnowledgeBase
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
from herhealth_backend.triage.age_bands import age_band_for
from herhealth_backend.triage.agent import (
    AttemptOutcome,
    Message,
    ReasoningAttempt,
    TriageAgent,
    render_known_background,
)
from herhealth_backend.triage.context import join_evidence
from herhealth_backend.triage.provenance import (
    drop_unknown_conditions,
    enforce_provenance_cap,
)
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
    #: Accepted and ignored. The model selector was removed (ADR 0018); the
    #: field stays so a client built before that does not get a 422.
    reasoning_model: str | None = None


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
    #: ``None`` on her own messages, and on every assistant turn recorded
    #: before migration 0010 — those are unattributable, not "the default
    #: model", and a reader of this field must not assume otherwise.
    served_by: dict[str, Any] | None = None
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
    than blocking the event loop for however long the reasoning model or
    retrieval takes to answer — the same reasoning
    ``app/main.py``'s ``_build_email_sender`` documents for its own blocking
    call inside an async context.
    """
    agent: TriageAgent | None = getattr(http_request.app.state, "triage_agent", None)
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "triage is not configured on this deployment "
                "(set HERHEALTH_TRIAGE_MODE=vllm for the local models, which also "
                "needs a retrieval index at HERHEALTH_INDEX_DIR, or demo for "
                "scripted replies)"
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
    long-lived HTTP client that the reasoning and retrieval clients each
    hold, reused across concurrent requests'
    executor threads, but this is not yet confirmed. ``asyncio.wait_for``
    below is a deliberate containment measure, not a fix: whatever is
    hanging still hangs, but the request now fails cleanly and promptly
    instead of hanging forever.

    Not holding the database session open across this call is worth keeping
    regardless of the above: a multi-second-to-multi-minute idle transaction
    during an unrelated external HTTP call is wasteful on its own terms.
    """
    loaded = await _load_session(request, user, database)
    session_id, history, carried = loaded.session_id, loaded.history, loaded.carried
    history.append(Message(role="user", content=request.message))
    background = await _known_background(user, database)

    # Her stored age band is an ANSWER, not just prose. Seeding the case
    # vector with it does two things the background block alone cannot:
    # `age_band` stops being offered as a question, and the value takes part
    # in the evidence join like any other answer.
    #
    # Observed live 2026-09-10 and the reason this exists: the background
    # block told the model "do not ask her age again" while the ranked
    # question menu — built from the case vector, which knew nothing about
    # her profile — offered `age_band` as its top entry, because age_band
    # separates 12 condition/value pairs and nothing marked it answered. The
    # prompt contradicted itself, and the model followed the half that named
    # a feature id. A rule stated in prose cannot beat a menu built from data.
    #
    # Profile is the weakest source: anything she has said in this
    # consultation wins, because the band is derived from a date she typed
    # once and her own words are about today.
    observed: dict[str, str] = {}
    profile_band = _profile_age_band(user)
    if profile_band is not None:
        observed["age_band"] = profile_band
    observed.update(loaded.observed)

    # The feature she was asked about last turn and has not yet answered. Her
    # incoming message is that answer, so a decision that does not record it
    # has dropped something she actually said — see _require_the_pending_answer.
    pending = next(
        (feature_id for feature_id in reversed(loaded.asked) if feature_id not in observed),
        None,
    )

    turn = None
    last_retryable_error: Exception | None = None
    # Calls made by turns this loop threw away. Kept because a discarded turn
    # still cost a real call to a real backend: dropping it would understate
    # how much work a turn took, and counting it as a success would overstate
    # how often that backend answered usefully.
    discarded: list[ReasoningAttempt] = []
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
                        observed=observed,
                        asked=loaded.asked,
                    ),
                ),
                timeout=REASONING_TIMEOUT_SECONDS,
            )
            # Repair before checking, not after: an invented condition name is
            # the one vocabulary fault worth surviving, because the field is
            # optional and the action code beside it is not. Everything else
            # the validator rejects — an unreal feature, an unreal rule, a
            # citation that was never retrieved — still fails the turn.
            turn = replace(
                turn, decision=drop_unknown_conditions(turn.decision, agent.base)
            )
            validate_against_knowledge_base(turn.decision, agent.base, turn.retrieved)
            _warn_if_the_pending_answer_was_dropped(turn.decision, pending)
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
            if turn is not None:
                discarded.extend(_mark_rejected(turn.attempts, error))
                turn = None
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
    payload = _decision_payload(
        decision, turn.retrieved, base=agent.base, observed=observed
    )
    served_by = _served_by_payload((*discarded, *turn.attempts))
    await _persist_turn(session_id, request.message, decision, payload, database, served_by)

    return {"session_id": str(session_id), "decision": payload, "served_by": served_by}


def _red_flag_citation(decision: TriageDecision, base: KnowledgeBase) -> dict[str, Any] | None:
    """The warning-sign rule a decision fired, as a citable source.

    Without this a red-flag conclusion shows **no sources at all**, which is
    the exact opposite of what it deserves: ``TriageDecision`` lets citations
    be empty precisely when ``red_flag_id`` is set, because ``red_flags.yaml``
    is deliberately never embedded or retrieved (see
    ``agent.render_red_flags``) and so produces no passage id to cite. The
    rule still carries a real ``source_id`` and a verbatim ``source_quote`` —
    the most load-bearing quote in the whole answer — and it was simply never
    rendered.

    **This is also the only route by which NHS can be cited, and that is a
    licence constraint, not an oversight.** NHS is ``citable_only``: its text
    may be quoted with attribution but may never enter the served corpus, so
    the served index is built without any NHS passage
    (``herhealth-data index``). Quoting a rule's ``source_quote`` with attribution is exactly the
    use its licence permits. Most of ``red_flags.yaml`` is NHS-derived, so in
    practice this is where NHS appears.

    The URL prefers the rule's own ``source_url`` — the page its
    ``source_quote`` was found in, verbatim — and falls back to the source's
    home page from ``sources.yaml`` when that is unknown. It used to be the
    home page always, which sent a woman reading a warning sign to nhs.uk
    rather than to the NHS page the warning sign is on.

    The fallback is not a formality: ``severe_pelvic_pain``'s quote appears on
    two NHS pages, so which one it was read from is genuinely unknown and it
    keeps the home-page link. A deep link there would be invented provenance,
    which is the thing the original comment here was right to refuse.
    """
    if decision.red_flag_id is None:
        return None
    rule = next((r for r in base.red_flags if r.id == decision.red_flag_id), None)
    if rule is None:
        return None
    source = base.sources_by_id.get(rule.source_id)
    url = rule.source_url or (source.url if source is not None else None)
    return {
        "id": rule.id,
        "text": rule.source_quote,
        "citation": f"{rule.source_id} § {rule.label}",
        "source_id": rule.source_id,
        "url": str(url) if url else None,
        "passage_type": "red_flag",
    }


def _warn_if_the_pending_answer_was_dropped(
    decision: TriageDecision, pending: str | None
) -> None:
    """Log when she answered a question and the answer was not recorded.

    The one case where a missing ``observed`` entry is provably wrong rather
    than merely suspicious: a feature was put to her last turn, her reply is
    the message just read, and the decision still does not say what she said.
    Her opening message is deliberately not covered — it may genuinely answer
    nothing, and guessing would turn "I feel unwell" into a failed request.

    **Warns rather than raises, and the choice is deliberate.** Raising would
    put this through the corrective-retry path, which costs a whole extra
    generation — 110-190s against the current provider — and, if the second
    attempt also forgot, would turn a usable answer into a 502. The harm from
    a dropped answer is that she gets asked the same question twice: annoying,
    not unsafe. The harm from a failed turn is that she gets nothing. The
    actual remedy is in the prompt, where ``observed`` now leads the output
    shape and carries a worked example; this is the instrument that says
    whether that worked.

    ``"unknown"`` counts as recorded: "I'm not sure" is an answer, and it is
    what stops the same question being asked again.
    """
    # An INFORM joins DECLINE here, for a different reason: she was asked
    # something and chose to ask a question back instead of answering, so the
    # pending feature is genuinely still open and nothing was dropped. The
    # feature stays on `asked`, so it is not re-offered, and she can answer it
    # next turn.
    if pending is None or decision.type in (DecisionType.DECLINE, DecisionType.INFORM):
        return
    if pending in decision.observed:
        return
    logger.warning(
        "dropped answer: she was asked about %r and the decision recorded "
        "nothing for it (observed=%s). She will be asked again.",
        pending,
        dict(decision.observed),
    )


def _evidence_citations(
    decision: TriageDecision, base: KnowledgeBase, observed: Mapping[str, str]
) -> list[dict[str, Any]]:
    """The authored evidence rows behind the conditions this decision named.

    **Why this exists.** A citation in this API is a ``PassageId`` — a hash of
    something the similarity search returned. That silently excludes the single
    largest body of reviewed clinical claims in the project: the 140 rows of
    ``evidence.csv``, which reach the model through
    ``context.join_evidence`` and never through retrieval at all. A conclusion
    could be grounded in four authored rows and still display "no sources".

    It matters most for NHS. NHS is ``citable_only``, so all 707 of its
    passages are filtered out of the served index — meaning **not one of its 47
    evidence rows could ever appear as a source**, however central it was to
    the answer. Quoting a row's ``source_quote`` with attribution is precisely
    what that licence permits, and it is what the row was authored as.

    Only rows the decision actually rests on are returned: rows keyed by an
    answer she gave, for a condition the model named. Nothing here widens the
    claim — it reports the join that already happened.
    """
    if not decision.matching_conditions:
        return []
    named = set(decision.matching_conditions)
    sources = base.sources_by_id
    citations: list[dict[str, Any]] = []
    for group in join_evidence(base, observed):
        if group.condition.id not in named:
            continue
        for row in group.supporting:
            source = sources.get(row.source_id)
            citations.append(
                {
                    "id": f"{row.condition_id}:{row.feature_id}:{row.value}",
                    "text": row.source_quote,
                    "citation": f"{row.source_id} § {group.condition.label}",
                    "source_id": row.source_id,
                    "url": str(source.url) if source is not None else None,
                    "passage_type": "evidence_row",
                }
            )
    return citations


def _decision_payload(
    decision: TriageDecision,
    retrieved: Sequence[RetrievedPassage],
    *,
    base: KnowledgeBase,
    observed: Mapping[str, str] | None = None,
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
    # The rule leads, when there is one: it is why the decision has the
    # urgency it has, so it outranks the background reading behind it.
    rule_citation = _red_flag_citation(decision, base)
    payload: dict[str, Any] = {
        **decision.model_dump(mode="json"),
        "cited_passages": [
            *([rule_citation] if rule_citation is not None else []),
            *_evidence_citations(decision, base, observed or {}),
            *[
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
        ],
    }
    return payload


def _profile_age_band(user: User) -> str | None:
    """Her age band from her stored date of birth, or ``None``.

    Derived on every turn rather than read from a column, so a consultation
    running on her birthday uses the band she is in today.
    """
    if user.date_of_birth is None:
        return None
    return age_band_for(user.date_of_birth, today=date.today())


async def _known_background(user: User, database: Database) -> str | None:
    """Her stored age band and health note, rendered for the system prompt.

    This is the one place the Accounts and Triage contexts meet over her
    profile, which ``CONTEXT-MAP.md`` permits only at the API layer — hence
    it living here and not inside ``TriageAgent``.

    The band is derived from her date of birth on every turn rather than
    read from a column, so a consultation that runs on her birthday uses the
    band she is in today. See ``triage.age_bands``.
    """
    age_band = _profile_age_band(user)
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


@dataclass(frozen=True, slots=True)
class LoadedSession:
    """Everything a turn needs from the stored consultation, as plain data."""

    session_id: uuid.UUID
    history: list[Message]

    #: Every passage this consultation has already cited. Without it, turn two
    #: of a live session 502s when the model re-cites turn-one evidence that
    #: this turn's retrieval did not return — see ``build_retrieval_query``.
    carried: tuple[RetrievedPassage, ...]

    #: The case vector, replayed from every stored decision's ``observed``.
    #: Rebuilt rather than stored on the session row so it stays derivable
    #: from the transcript — the same discipline that replays the verbatim
    #: history rather than summarising it. A later turn's reading of a
    #: feature overwrites an earlier one, which is why this is applied in
    #: chronological order.
    observed: dict[str, str]

    #: Features already put to her, whether or not she could answer. Kept
    #: separate from ``observed`` because "asked and she said unknown" and
    #: "asked and she answered" must both stop the screen re-offering the
    #: same probe, while only the second one can satisfy a clause.
    asked: list[str]


async def _load_session(
    request: TriageTurnRequest, user: User, database: Database
) -> LoadedSession:
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
            return LoadedSession(
                session_id=consultation.id, history=[], carried=(), observed={}, asked=[]
            )

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
        observed: dict[str, str] = {}
        asked: list[str] = []
        for row in rows:
            history.append(Message(role=row.role, content=row.content))
            if row.role != "assistant" or not isinstance(row.decision, dict):
                continue
            for raw in row.decision.get("cited_passages") or []:
                passage = _passage_from_cited(raw)
                if passage is not None:
                    carried_by_id.setdefault(passage.id, passage)
            stored_observed = row.decision.get("observed")
            if isinstance(stored_observed, dict):
                observed.update(
                    {
                        str(k): str(v)
                        for k, v in stored_observed.items()
                        if isinstance(k, str) and isinstance(v, str)
                    }
                )
            feature_id = row.decision.get("next_feature_id")
            if isinstance(feature_id, str):
                asked.append(feature_id)
        return LoadedSession(
            session_id=consultation.id,
            history=history,
            carried=tuple(carried_by_id.values()),
            observed=observed,
            asked=asked,
        )


def _mark_rejected(
    attempts: Sequence[ReasoningAttempt], error: Exception
) -> list[ReasoningAttempt]:
    """Relabel a discarded turn's successful call as ``REJECTED``.

    The client was happy — it returned a schema-valid ``TriageDecision`` —
    and this layer refused it anyway, because the decision named a feature,
    rule or citation that is not in the knowledge base. Only the last
    successful call is relabelled: the earlier entries in the trail are
    failures already, and their reasons are their own.
    """
    marked = list(attempts)
    for index in range(len(marked) - 1, -1, -1):
        if marked[index].outcome is AttemptOutcome.OK:
            marked[index] = replace(
                marked[index],
                outcome=AttemptOutcome.REJECTED,
                detail=_attempt_detail(error),
            )
            break
    return marked


def _attempt_detail(error: Exception) -> str:
    """A short reason, capped — this is read by a human out of a database."""
    text = str(error).strip() or type(error).__name__
    return text if len(text) <= 200 else f"{text[:199]}…"


def _served_by_payload(attempts: Sequence[ReasoningAttempt]) -> dict[str, Any] | None:
    """The attribution record stored on the turn and returned to the caller.

    ``final`` is the backend whose decision she actually read — the last one
    that succeeded, which on a fallback is **not** the one tried first.
    ``attempts`` is every call the turn took, in order, so a fallback rate can
    be measured from the stored rows rather than estimated from server logs.

    ``None`` when nothing reported an attempt, which is what a client
    predating this contract looks like. Reported as unknown, never as a
    default model.
    """
    if not attempts:
        return None
    final: str | None = None
    for attempt in reversed(attempts):
        if attempt.outcome is AttemptOutcome.OK:
            final = attempt.client
            break
    return {
        "final": final,
        "attempts": [
            {
                "client": attempt.client,
                "outcome": attempt.outcome.value,
                "detail": attempt.detail,
            }
            for attempt in attempts
        ],
    }


async def _persist_turn(
    session_id: uuid.UUID,
    user_message: str,
    decision: TriageDecision,
    payload: dict[str, Any],
    database: Database,
    served_by: dict[str, Any] | None = None,
) -> None:
    """A second short-lived session: write this turn's two messages, and
    close out the consultation if it concluded.

    Stores ``payload`` — the decision *with* its resolved
    ``cited_passages`` (see :func:`_decision_payload`) — not the bare
    decision. Reopening an old consultation from the sidebar therefore
    shows the same quoted sources it showed live, without re-running a
    retrieval that might not return the same passages today.
    """
    # Each shape keeps its user-facing text in its own field, and the schema
    # settles which one is filled: question_text on an ask, answer_text on an
    # inform, rationale on a conclude or a decline. The `or` fallbacks guard a
    # NOT NULL column against a shape that somehow arrived empty; they are not
    # a real branch.
    #
    # Neither a decline nor an inform reaches the status change below, and for
    # the same reason in both cases: an off-scope message must not burn her
    # consultation, and neither must a question she asked along the way. The
    # session stays active and the composer stays open.
    if decision.type is DecisionType.ASK:
        assistant_content = decision.question_text or decision.rationale
    elif decision.type is DecisionType.INFORM:
        assistant_content = decision.answer_text or decision.rationale
    else:
        assistant_content = decision.rationale
    async with database.session() as session:
        session.add(MessageRow(session_id=session_id, role="user", content=user_message))
        session.add(
            MessageRow(
                session_id=session_id,
                role="assistant",
                content=assistant_content,
                decision=payload,
                # Beside the decision, never inside it — see the column's own
                # note in app/triage/models.py.
                served_by=served_by,
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
                        served_by=row.served_by,
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
