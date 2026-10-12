"""The FastAPI application: how the service boots and the one route it has.

:func:`create_app` is a factory rather than a module-level ``app`` so a test can
build an application bound to a throwaway database and never touch the real one.
Pass a :class:`~herhealth_backend.app.db.Database` in and the app uses it as-is;
pass nothing and the lifespan builds one from the environment at start-up and
disposes it at shutdown.

The only endpoint is ``/health``, and it is a real health check: it asks the
database a question and reports 503 if the answer does not come back. A skeleton
that returns 200 because the process is alive tells you nothing you did not
already know from the fact that it answered at all.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from typing import Any

from anyio import to_thread
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from herhealth_contracts.decision import TriageDecision
from herhealth_contracts.knowledge import KnowledgeBase
from herhealth_contracts.loading import load_knowledge_base
from herhealth_contracts.retrieval import RetrievedPassage
from sqlalchemy.exc import SQLAlchemyError

from herhealth_backend.app.accounts.email_sender import (
    ConsoleEmailSender,
    EmailSender,
    SesEmailSender,
)
from herhealth_backend.app.accounts.error_handlers import register_error_handlers
from herhealth_backend.app.accounts.google_identity import (
    GoogleOAuthTokenVerifier,
    GoogleTokenVerifier,
    UnconfiguredGoogleTokenVerifier,
)
from herhealth_backend.app.accounts.routes import router as accounts_router
from herhealth_backend.app.config import EMAIL_SENDER_ENV, database_url
from herhealth_backend.app.config import answer_model as configured_answer_model
from herhealth_backend.app.config import cors_origins as configured_cors_origins
from herhealth_backend.app.config import decision_model as configured_decision_model
from herhealth_backend.app.config import email_sender_kind as configured_email_sender_kind
from herhealth_backend.app.config import google_client_id as configured_google_client_id
from herhealth_backend.app.config import knowledge_dir as configured_knowledge_dir
from herhealth_backend.app.config import session_secret as configured_session_secret
from herhealth_backend.app.config import triage_mode as configured_triage_mode
from herhealth_backend.app.config import vllm_api_key as configured_vllm_api_key
from herhealth_backend.app.config import vllm_max_attempts as configured_vllm_max_attempts
from herhealth_backend.app.config import vllm_timeout as configured_vllm_timeout
from herhealth_backend.app.config import vllm_url as configured_vllm_url
from herhealth_backend.app.db import Database
from herhealth_backend.app.triage.routes import router as triage_router
from herhealth_backend.triage.agent import RetrievalClient, TriageAgent
from herhealth_backend.triage.chain import (
    ANSWER_MAX_TOKENS,
    DECIDE_MAX_TOKENS,
    EXTRACT_MAX_TOKENS,
    LangChainAnswerWriter,
    LangChainFeatureExtractor,
    LangChainReasoningClient,
    build_chat_model,
)
from herhealth_backend.triage.clients import DecisionValidator
from herhealth_backend.triage.demo_clients import MvpDemoReasoningClient, StaticRetrievalClient
from herhealth_backend.triage.retrieval import (
    IndexRefused,
    LangChainRetrievalClient,
    RetrievalSettings,
)
from herhealth_backend.triage.vocabulary import validate_against_knowledge_base

__all__ = ["create_app"]

logger = logging.getLogger(__name__)


def _build_email_sender() -> EmailSender:
    """Construct the configured EmailSender. Synchronous — ``SesEmailSender``'s
    ``boto3.client(...)`` call can resolve credentials over the network (an
    EC2/ECS instance-metadata probe, off that hardware, is not fast), so this
    always runs through ``to_thread.run_sync`` rather than being called
    directly on the event loop. See :func:`create_app`'s ``lifespan``.
    """
    kind = configured_email_sender_kind()
    if kind == "ses":
        return SesEmailSender()
    if kind == "console":
        return ConsoleEmailSender()
    raise RuntimeError(f"{EMAIL_SENDER_ENV}={kind!r} is not recognised. Use 'console' or 'ses'.")


def _decision_validator(base: KnowledgeBase) -> DecisionValidator:
    """``validate_against_knowledge_base``, bound to this deployment's
    knowledge base, in the shape a reasoning client accepts.

    Handing this to a client moves the closed-vocabulary check inside that
    client's own retry loop, where a violation becomes corrective feedback to
    the model and, failing that, a fallback to another model. Before this
    existed the check ran only in ``app/triage/routes.py``, after the client
    had returned — too late to correct and too late to fail over, which made
    an invented condition id (``menopause`` for ``perimenopause``, observed
    2026-09-09) a user-visible 502. The route still validates, as a backstop
    for any client built without this.
    """

    def validate(decision: TriageDecision, context: Sequence[RetrievedPassage]) -> None:
        validate_against_knowledge_base(decision, base, context)

    return validate


def _build_retrieval() -> RetrievalClient | None:
    """The retriever for this deployment, or ``None`` when it has no usable
    index. ``None`` is not an error: triage is one feature of this backend,
    and a host without an index still serves accounts and the rest — the turn
    route answers 503 "not configured", the way it does without a reasoning
    model. The reason is logged, so it is never silent.
    """
    try:
        return LangChainRetrievalClient.from_settings(RetrievalSettings.from_env())
    except IndexRefused as error:
        logger.warning("triage retrieval is not configured: %s", error)
        return None


#: How many of her answers a real deployment wants recorded before it accepts
#: a conclusion without challenge. Three is deliberately low — enough to stop a
#: verdict from one sentence, not enough to make a consultation feel like a
#: form. See ``TriageAgent._refuse_premature_conclusion``: the model still
#: decides, this only sends an early conclusion back once with the reason.
MIN_ANSWERS_BEFORE_CONCLUDING = 3


def _build_triage_agent() -> TriageAgent | None:
    """Construct the triage agent for this deployment's mode.

    ``off`` disables triage. ``demo`` wires offline scripted clients — no
    network, no GPU, no index. ``vllm`` is the real path (ADR 0018): the
    retriever over the index on disk, then the local models through LangChain
    — the base model extracts what she said and decides, and the fine-tuned
    adapter words informational answers. There is no second provider behind
    them.

    ``None`` also when ``vllm`` is asked for but there is no usable index:
    the turn route then answers 503 "not configured".
    """
    mode = configured_triage_mode()
    if mode == "off":
        return None
    base = load_knowledge_base(configured_knowledge_dir())
    if mode == "demo":
        # Demo mode keeps the gates off: MvpDemoReasoningClient is scripted and
        # has no second answer to give when a reply is sent back.
        return TriageAgent(
            base=base,
            reasoning=MvpDemoReasoningClient(),
            retrieval=StaticRetrievalClient(),
        )

    retrieval = _build_retrieval()
    if retrieval is None:
        return None

    def chat(model: str, max_tokens: int) -> Any:
        return build_chat_model(
            url=configured_vllm_url(),
            model=model,
            api_key=configured_vllm_api_key(),
            timeout=configured_vllm_timeout(),
            max_tokens=max_tokens,
        )

    deciding = configured_decision_model()
    answering = configured_answer_model()
    return TriageAgent(
        base=base,
        retrieval=retrieval,
        reasoning=LangChainReasoningClient(
            chat(deciding, DECIDE_MAX_TOKENS),
            name=deciding,
            validator=_decision_validator(base),
            max_attempts=configured_vllm_max_attempts(),
        ),
        extractor=LangChainFeatureExtractor(chat(deciding, EXTRACT_MAX_TOKENS), base),
        answer_writer=(
            LangChainAnswerWriter(chat(answering, ANSWER_MAX_TOKENS), name=answering)
            if answering
            else None
        ),
        min_answers=MIN_ANSWERS_BEFORE_CONCLUDING,
        refuse_inform_with_symptoms=True,
    )


def _build_google_verifier() -> GoogleTokenVerifier:
    """Construct the configured GoogleTokenVerifier. Unlike ``_build_email_sender``,
    there is no eagerly-blocking client to build here — ``GoogleOAuthTokenVerifier``
    only does network I/O per call to ``verify``, already offloaded there —
    so this needs no ``to_thread`` wrapper of its own.
    """
    client_id = configured_google_client_id()
    if client_id is None:
        return UnconfiguredGoogleTokenVerifier()
    return GoogleOAuthTokenVerifier(client_id=client_id)


def create_app(
    database: Database | None = None,
    session_secret: str | None = None,
    email_sender: EmailSender | None = None,
    google_verifier: GoogleTokenVerifier | None = None,
    triage_agent: TriageAgent | None = None,
) -> FastAPI:
    """Build the application.

    When ``database`` is given the caller owns its lifecycle — the app will not
    dispose it. When it is ``None`` the app creates one from
    :func:`~herhealth_backend.app.config.database_url` on start-up and disposes
    it on shutdown. ``session_secret`` (the key access tokens are signed with,
    see ``app/accounts/tokens.py``) is read from
    :func:`~herhealth_backend.app.config.session_secret` when not given.
    ``email_sender`` (see ``app/accounts/email_sender.py``) defaults to
    whatever ``HERHEALTH_EMAIL_SENDER`` selects
    (:func:`~herhealth_backend.app.config.email_sender_kind`) — ``"console"``
    (the default) or ``"ses"``, the real sender. ``google_verifier`` (see
    ``app/accounts/google_identity.py``) defaults to a real
    ``GoogleOAuthTokenVerifier`` when ``HERHEALTH_GOOGLE_CLIENT_ID`` is set,
    or an ``UnconfiguredGoogleTokenVerifier`` otherwise — Google sign-in is
    optional, so its absence never stops the app from booting. ``triage_agent``
    (see ``app/triage/routes.py``) defaults to a real ``TriageAgent`` wired to
    the local models and the retrieval index in ``vllm`` mode, or
    ``None`` otherwise — triage is likewise optional; ``POST /triage/turn``
    returns 503 rather than the app refusing to start. The one exception is an
    unrecognised ``HERHEALTH_TRIAGE_MODE``, which stops start-up with the valid
    modes named, so a host left on a removed mode is told instead of silently
    losing triage.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        owns_database = getattr(app.state, "database", None) is None
        if owns_database:
            app.state.database = Database(database_url())
        if getattr(app.state, "session_secret", None) is None:
            app.state.session_secret = configured_session_secret()
        if getattr(app.state, "email_sender", None) is None:
            app.state.email_sender = await to_thread.run_sync(_build_email_sender)
        if getattr(app.state, "google_verifier", None) is None:
            app.state.google_verifier = _build_google_verifier()
        if getattr(app.state, "triage_agent", None) is None:
            app.state.triage_agent = _build_triage_agent()
        try:
            yield
        finally:
            if owns_database:
                await app.state.database.dispose()

    app = FastAPI(title="HerHealthGPT backend", lifespan=lifespan)
    origins = configured_cors_origins()
    if origins:
        # Credentialed (cookie-based) cross-origin requests — needed only
        # when a frontend calls this API from a different origin than the
        # Next.js rewrite proxy's same-origin default. allow_origins is
        # never "*" here: credentials: "include" plus a wildcard origin is
        # what the fetch spec forbids outright, not a preference.
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    if database is not None:
        app.state.database = database
    if session_secret is not None:
        app.state.session_secret = session_secret
    if email_sender is not None:
        app.state.email_sender = email_sender
    if google_verifier is not None:
        app.state.google_verifier = google_verifier
    if triage_agent is not None:
        app.state.triage_agent = triage_agent
    register_error_handlers(app)
    app.include_router(accounts_router)
    app.include_router(triage_router)

    @app.get("/health")
    async def health(request: Request) -> JSONResponse:
        db: Database = request.app.state.database
        try:
            await db.ping()
        except (SQLAlchemyError, OSError):
            return JSONResponse({"status": "unavailable"}, status_code=503)
        return JSONResponse({"status": "ok"}, status_code=200)

    return app
