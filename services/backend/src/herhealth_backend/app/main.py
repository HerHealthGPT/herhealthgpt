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

from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager

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
from herhealth_backend.app.config import cors_origins as configured_cors_origins
from herhealth_backend.app.config import email_sender_kind as configured_email_sender_kind
from herhealth_backend.app.config import google_client_id as configured_google_client_id
from herhealth_backend.app.config import knowledge_dir as configured_knowledge_dir
from herhealth_backend.app.config import model_selector_enabled as configured_model_selector_enabled
from herhealth_backend.app.config import model_service_url as configured_model_service_url
from herhealth_backend.app.config import openrouter_api_key as configured_openrouter_api_key
from herhealth_backend.app.config import session_secret as configured_session_secret
from herhealth_backend.app.config import triage_mode as configured_triage_mode
from herhealth_backend.app.config import vllm_api_key as configured_vllm_api_key
from herhealth_backend.app.config import vllm_configured as configured_vllm_configured
from herhealth_backend.app.config import vllm_max_attempts as configured_vllm_max_attempts
from herhealth_backend.app.config import vllm_model as configured_vllm_model
from herhealth_backend.app.config import vllm_timeout as configured_vllm_timeout
from herhealth_backend.app.config import vllm_url as configured_vllm_url
from herhealth_backend.app.db import Database
from herhealth_backend.app.triage.reasoning_models import (
    BASE_MODEL_ID,
    FINE_TUNED_MODEL_ID,
    ReasoningModelOption,
)
from herhealth_backend.app.triage.routes import router as triage_router
from herhealth_backend.triage.agent import ReasoningClient, TriageAgent
from herhealth_backend.triage.clients import (
    DecisionValidator,
    FallbackReasoningClient,
    HttpRetrievalClient,
    OpenRouterReasoningClient,
    VllmReasoningClient,
)
from herhealth_backend.triage.demo_clients import MvpDemoReasoningClient, StaticRetrievalClient
from herhealth_backend.triage.vocabulary import validate_against_knowledge_base

__all__ = ["create_app"]


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


def _build_triage_agent() -> TriageAgent | None:
    """Construct the triage agent for this deployment's mode.

    ``HERHEALTH_TRIAGE_MODE=demo`` (the local-MVP default when no OpenRouter
    key is set) wires offline scripted clients — no network, no GPU. ``off``
    disables triage entirely. ``openrouter`` needs ``OPENROUTER_API_KEY`` and
    a running ``services/model``. ``vllm`` tries ``HERHEALTH_VLLM_URL`` first
    and falls back to OpenRouter when ``OPENROUTER_API_KEY`` is also set —
    which is the single-path shape used when the model selector is off and
    the fine-tuned adapter is the only model offered.
    """
    mode = configured_triage_mode()
    base = load_knowledge_base(configured_knowledge_dir())
    retrieval = HttpRetrievalClient(base_url=configured_model_service_url())
    validator = _decision_validator(base)

    if mode == "off":
        return None
    if mode == "demo":
        return TriageAgent(
            base=base,
            reasoning=MvpDemoReasoningClient(),
            retrieval=StaticRetrievalClient(),
        )

    if mode == "vllm":
        primary = VllmReasoningClient(
            base_url=configured_vllm_url(),
            model=configured_vllm_model(),
            api_key=configured_vllm_api_key(),
            decision_validator=validator,
            timeout=configured_vllm_timeout(),
            max_attempts=configured_vllm_max_attempts(),
        )
        api_key = configured_openrouter_api_key()
        reasoning: ReasoningClient
        if api_key is None:
            reasoning = primary
        else:
            reasoning = FallbackReasoningClient(
                primary=primary,
                fallback=OpenRouterReasoningClient(
                    api_key=api_key, decision_validator=validator
                ),
                primary_name="fine-tuned adapter (campus vLLM)",
                fallback_name="base model (OpenRouter)",
            )
        return TriageAgent(base=base, reasoning=reasoning, retrieval=retrieval)

    api_key = configured_openrouter_api_key()
    if api_key is None:
        return None
    return TriageAgent(
        base=base,
        reasoning=OpenRouterReasoningClient(api_key=api_key, decision_validator=validator),
        retrieval=retrieval,
    )


def _build_reasoning_models() -> dict[str, ReasoningModelOption]:
    """The models ``GET /triage/models`` offers and ``POST /triage/turn`` may
    route to.

    Empty unless ``HERHEALTH_MODEL_SELECTOR`` is on: without it the app has
    exactly one reasoning path, chosen by ``HERHEALTH_TRIAGE_MODE``, and the
    selector is invisible rather than present-but-disabled. That is the
    dev-only scoping ADR 0016 asks for — the fine-tuned adapter must not be
    reachable at all in a deployment someone is being shown.

    An option appears only when it is actually configured, so the frontend
    never lists a model that would fail on the first request.
    """
    if not configured_model_selector_enabled():
        return {}

    validator = _decision_validator(load_knowledge_base(configured_knowledge_dir()))
    options: dict[str, ReasoningModelOption] = {}

    openrouter_key = configured_openrouter_api_key()
    if openrouter_key is not None:
        options[BASE_MODEL_ID] = ReasoningModelOption(
            id=BASE_MODEL_ID,
            label="Base model",
            description="Qwen3.5-9B as published, with no fine-tuning. The default.",
            reviewed=True,
            client=OpenRouterReasoningClient(
                api_key=openrouter_key, decision_validator=validator
            ),
        )

    if configured_vllm_configured():
        # The adapter answers first; the base model answers instead when the
        # adapter is unreachable or returns nothing that validates. Measured
        # 2026-09-09, roughly one in four in-scope turns against the adapter
        # alone ended in a 502 — see FallbackReasoningClient's docstring for
        # the failure breakdown and for what this does and does not fix.
        fine_tuned_client: ReasoningClient = VllmReasoningClient(
            base_url=configured_vllm_url(),
            model=configured_vllm_model(),
            api_key=configured_vllm_api_key(),
            decision_validator=validator,
            timeout=configured_vllm_timeout(),
            max_attempts=configured_vllm_max_attempts(),
        )
        if openrouter_key is not None:
            fine_tuned_client = FallbackReasoningClient(
                primary=fine_tuned_client,
                fallback=OpenRouterReasoningClient(
                    api_key=openrouter_key, decision_validator=validator
                ),
                primary_name="fine-tuned adapter (campus vLLM)",
                fallback_name="base model (OpenRouter)",
            )
        options[FINE_TUNED_MODEL_ID] = ReasoningModelOption(
            id=FINE_TUNED_MODEL_ID,
            label="Fine-tuned model",
            description=(
                "Our QLoRA adapter, served on the campus GPU, with the base "
                "model as an automatic fallback when it cannot produce an "
                "answer. It was trained on phrasing rather than on multi-turn "
                "conversation, so it tends to conclude before asking."
            ),
            # Selecting this no longer labels each answer in the UI. The
            # remaining control on reachability is HERHEALTH_MODEL_SELECTOR,
            # which is off by default: ADR 0016 scopes this option to dev, so
            # it is absent — not merely unlabelled — in any deployment being
            # shown to someone. `default_model_id` still resolves to the base
            # model because that option is inserted first.
            reviewed=True,
            client=fine_tuned_client,
        )

    return options


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
    OpenRouter and ``services/model`` when ``OPENROUTER_API_KEY`` is set, or
    ``None`` otherwise — triage is likewise optional; ``POST /triage/turn``
    returns 503 rather than the app refusing to start.
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
        if getattr(app.state, "reasoning_models", None) is None:
            app.state.reasoning_models = _build_reasoning_models()
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
