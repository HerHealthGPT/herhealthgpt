"""Where the running process reads its configuration from.

One value for now — the database URL — but kept in its own module so the app
never reaches into ``os.environ`` in scattered places. The URL is required at
run time and has no default: a service that silently falls back to a local
database is a service that can point at the wrong one in production without
anyone noticing. Tests never read this; they pass a container URL straight to
:class:`~herhealth_backend.app.db.Database`.
"""

from __future__ import annotations

import os
from pathlib import Path

__all__ = [
    "DATABASE_URL_ENV",
    "database_url",
    "SESSION_SECRET_ENV",
    "MIN_SESSION_SECRET_LENGTH",
    "session_secret",
    "EMAIL_SENDER_ENV",
    "email_sender_kind",
    "GOOGLE_CLIENT_ID_ENV",
    "google_client_id",
    "KNOWLEDGE_DIR_ENV",
    "knowledge_dir",
    "MODEL_SERVICE_URL_ENV",
    "model_service_url",
    "MODEL_SELECTOR_ENV",
    "model_selector_enabled",
    "OPENROUTER_API_KEY_ENV",
    "openrouter_api_key",
    "TRIAGE_MODE_ENV",
    "triage_mode",
    "VLLM_API_KEY_ENV",
    "VLLM_MODEL_ENV",
    "VLLM_URL_ENV",
    "vllm_api_key",
    "vllm_configured",
    "reasoning_timeout",
    "vllm_max_attempts",
    "vllm_model",
    "vllm_timeout",
    "vllm_url",
    "COOKIE_SECURE_ENV",
    "cookie_secure",
    "CORS_ORIGINS_ENV",
    "cors_origins",
]

#: The one environment variable the process reads to find its database. Namespaced
#: so it cannot collide with a bare ``DATABASE_URL`` some other tool sets.
DATABASE_URL_ENV = "HERHEALTH_DATABASE_URL"

#: The environment variable holding the key access tokens are signed with —
#: see app/accounts/tokens.py. Every process that verifies a token needs the
#: same value, so it is configuration, not something generated at start-up.
SESSION_SECRET_ENV = "HERHEALTH_SESSION_SECRET"

#: Below this many characters, a secret is refused outright — this key signs
#: every access token in the system, and a short or guessable one lets an
#: attacker forge tokens for any user, the same reasoning password_policy.py's
#: MIN_LENGTH applies to a single account. `openssl rand -hex 32` (the value
#: this project's own docs recommend) produces 64 characters, comfortably
#: past this floor; a short human-typed value is what this actually catches.
MIN_SESSION_SECRET_LENGTH = 32

#: Which EmailSender app/main.py constructs — see app/accounts/email_sender.py.
EMAIL_SENDER_ENV = "HERHEALTH_EMAIL_SENDER"

#: The OAuth client this backend is registered as with Google — needed to
#: check an ID token's audience. See app/accounts/google_identity.py.
GOOGLE_CLIENT_ID_ENV = "HERHEALTH_GOOGLE_CLIENT_ID"


def database_url() -> str:
    """The SQLAlchemy URL for the application database.

    Expected form ``postgresql+psycopg://user:password@host:port/name`` — the
    ``+psycopg`` driver marker matters, because the engine is async and psycopg 3
    is what backs it. Raises rather than guessing when the variable is unset.
    """
    url = os.environ.get(DATABASE_URL_ENV)
    if not url:
        raise RuntimeError(
            f"{DATABASE_URL_ENV} is not set. The backend needs a PostgreSQL URL, "
            "e.g. postgresql+psycopg://user:password@localhost:5432/herhealth."
        )
    return url


def session_secret() -> str:
    """The key used to sign access tokens.

    Raises rather than defaulting, for the same reason :func:`database_url`
    does: a process that invented its own key at start-up could not verify a
    token another instance issued, and a fixed built-in default would let
    every deployment forge every other deployment's tokens.

    The length check below is a floor, not an entropy check — it catches a
    forgotten value or a short human-typed one, the same class of mistake
    password_policy.py's MIN_LENGTH catches for a password. It cannot catch
    a 32-character value that is still guessable (all one character, a
    repeated word); nothing here measures that. Generate this value with
    `openssl rand -hex 32` and the floor is moot.
    """
    secret = os.environ.get(SESSION_SECRET_ENV)
    if not secret:
        raise RuntimeError(
            f"{SESSION_SECRET_ENV} is not set. The backend needs a long random "
            "string to sign access tokens, e.g. via `openssl rand -hex 32`."
        )
    if len(secret) < MIN_SESSION_SECRET_LENGTH:
        raise RuntimeError(
            f"{SESSION_SECRET_ENV} is only {len(secret)} characters long; it needs "
            f"at least {MIN_SESSION_SECRET_LENGTH}, e.g. via `openssl rand -hex 32`."
        )
    return secret


def email_sender_kind() -> str:
    """Which EmailSender to construct: ``"console"`` (the default — logs
    instead of sending, see ``app/accounts/email_sender.py``) or ``"ses"``
    (sends for real). Unlike :func:`database_url` and :func:`session_secret`,
    this has a safe default: a process that never sets
    ``HERHEALTH_EMAIL_SENDER`` behaves exactly as every environment did
    before this variable existed. Validating the value is ``app/main.py``'s
    job, the same way it — not this module — decides what to build from
    ``database_url()``'s string.
    """
    return os.environ.get(EMAIL_SENDER_ENV, "console")


#: Where the seven knowledge files live. Same variable name the CLI
#: (herhealth_backend.triage.cli) and the Makefile's `triage`/`eval` targets
#: already use — one variable, so a dev box that has it set for the CLI has
#: it set for the API too.
KNOWLEDGE_DIR_ENV = "HERHEALTH_KNOWLEDGE_DIR"

#: services/model's base URL — see docs/adr/0012. Defaults to that service's
#: own default port, so a dev box running both processes needs nothing set.
MODEL_SERVICE_URL_ENV = "HERHEALTH_MODEL_SERVICE_URL"

#: OpenRouterReasoningClient's key (triage/clients.py, ADR 0012). Optional at
#: the app level, the same way GOOGLE_CLIENT_ID_ENV is: triage is one feature
#: of this backend, not the whole of it, so its absence degrades one route
#: to "not configured" rather than stopping the app from booting at all.
OPENROUTER_API_KEY_ENV = "OPENROUTER_API_KEY"

#: How triage is wired at boot. ``demo`` uses offline scripted clients (no
#: OpenRouter, no services/model) for local MVP testing. ``openrouter`` needs
#: OPENROUTER_API_KEY and a running services/model. ``vllm`` tries a
#: self-hosted vLLM server (HERHEALTH_VLLM_URL) and falls back to OpenRouter
#: when OPENROUTER_API_KEY is also set. ``off`` disables triage.
TRIAGE_MODE_ENV = "HERHEALTH_TRIAGE_MODE"

#: Self-hosted vLLM OpenAI-compatible API (see docs/runbooks/dev-vllm-lora-endpoint.md).
#: Port 8002 by default — services/model retrieval uses 8001.
VLLM_URL_ENV = "HERHEALTH_VLLM_URL"
VLLM_MODEL_ENV = "HERHEALTH_VLLM_MODEL"

#: Bearer token for the vLLM server, when it was started with ``--api-key``.
#: Optional: a server on a trusted LAN or behind an SSH tunnel needs none,
#: and sending an empty Authorization header would be worse than sending
#: nothing. See triage/clients.py's VllmReasoningClient.
VLLM_API_KEY_ENV = "HERHEALTH_VLLM_API_KEY"

#: Seconds to wait on one vLLM request before giving up and failing over.
#: Deliberately BELOW the reverse proxy's own cut-off — see
#: :func:`vllm_timeout`.
VLLM_TIMEOUT_ENV = "HERHEALTH_VLLM_TIMEOUT"

#: How many times the vLLM client re-prompts itself before failing over.
VLLM_MAX_ATTEMPTS_ENV = "HERHEALTH_VLLM_MAX_ATTEMPTS"

#: Whole-turn budget in the triage route, in seconds.
REASONING_TIMEOUT_ENV = "HERHEALTH_REASONING_TIMEOUT"

#: Whether ``GET /triage/models`` offers more than the default model, letting
#: a caller choose per turn. Off by default and deliberately dev-only: the
#: fine-tuned adapter is not cleared to make triage decisions (CLAUDE.md, and
#: docs/runbooks/dev-vllm-lora-endpoint.md §6), so a marker or a supervisor
#: opening this app must see one model and no switch. See ADR 0016.
MODEL_SELECTOR_ENV = "HERHEALTH_MODEL_SELECTOR"

#: Auth cookies' ``secure`` flag. Defaults to true; set ``false`` for plain-HTTP
#: local dev (http://localhost) so browsers store and send session cookies.
COOKIE_SECURE_ENV = "HERHEALTH_COOKIE_SECURE"


def knowledge_dir() -> Path:
    """Where to load the knowledge base from. Defaults to ``knowledge/``
    resolved from the current working directory, matching every Makefile
    target that runs this process from the repo root.
    """
    return Path(os.environ.get(KNOWLEDGE_DIR_ENV, "knowledge"))


def model_service_url() -> str:
    """Base URL for ``services/model`` (see docs/adr/0012). No required-value
    check like :func:`database_url`'s: an unreachable url fails at the first
    request, loudly, from ``HttpRetrievalClient`` — there is no silent wrong
    default to guard against the way a database URL has one.
    """
    return os.environ.get(MODEL_SERVICE_URL_ENV, "http://127.0.0.1:8001")


def openrouter_api_key() -> str | None:
    """The OpenRouter API key, or ``None`` if triage is not configured on
    this deployment. Unlike :func:`database_url` and :func:`session_secret`,
    absence is not an error — see ``app/triage/routes.py``, which returns a
    clear 503 instead of failing app start-up.
    """
    return os.environ.get(OPENROUTER_API_KEY_ENV) or None


def triage_mode() -> str:
    """``demo``, ``openrouter``, ``vllm``, or ``off``. Defaults to ``openrouter`` when a
    key is set, otherwise ``off``. Set ``HERHEALTH_TRIAGE_MODE=demo`` explicitly
    for local MVP testing without OpenRouter or services/model.
    """
    explicit = os.environ.get(TRIAGE_MODE_ENV, "").strip().lower()
    if explicit in {"demo", "openrouter", "vllm", "off"}:
        return explicit
    if openrouter_api_key():
        return "openrouter"
    return "off"


def vllm_url() -> str:
    """Base URL for the self-hosted vLLM server (no path suffix)."""
    return os.environ.get(VLLM_URL_ENV, "http://127.0.0.1:8002")


def vllm_model() -> str:
    """The ``model`` field sent to vLLM — typically the LoRA module name."""
    return os.environ.get(VLLM_MODEL_ENV, "herhealth")


def vllm_api_key() -> str | None:
    """Bearer token for the vLLM server, or ``None`` when it needs none."""
    return os.environ.get(VLLM_API_KEY_ENV) or None


def reasoning_timeout() -> float:
    """Seconds one triage turn may take end to end. Default 150.

    Raise this only alongside :func:`vllm_timeout`, and only if the network
    path actually allows it. On the campus route it does not: JupyterHub's
    reverse proxy cuts at roughly 60 seconds regardless of what this says,
    so a larger budget here buys nothing on its own — it just means the
    backend waits longer for a request the proxy has already killed.

    The ceiling that matters is the smallest one on the path, and it is not
    ours.
    """
    raw = os.environ.get(REASONING_TIMEOUT_ENV, "").strip()
    if not raw:
        return 150.0
    try:
        value = float(raw)
    except ValueError:
        return 150.0
    return value if value > 0 else 150.0


def vllm_timeout() -> float:
    """Seconds to wait on one vLLM request. Default 50.

    **This number exists to lose a race on purpose.** The campus endpoint is
    reached through JupyterHub's reverse proxy, which cuts a request at
    roughly 60 seconds and answers ``504 Gateway Time-out``. A turn that is
    merely slow — 30-120s is normal for this adapter — was therefore
    indistinguishable from a broken one, and the user saw "a service we rely
    on is temporarily unavailable".

    Timing out at 50s means *we* give up first, deterministically, and get a
    clean ``httpx.ReadTimeout`` that ``FallbackReasoningClient`` fails over
    on. Waiting for the proxy's 504 also fails over — 504 is in the
    retryable set — but only after burning the full 60s, and only if the
    proxy actually answers rather than dropping the connection.

    Raise it only if the proxy's own limit is known to be higher. A value
    above that limit hands control back to the proxy and undoes this.
    """
    raw = os.environ.get(VLLM_TIMEOUT_ENV, "").strip()
    if not raw:
        return 50.0
    try:
        value = float(raw)
    except ValueError:
        return 50.0
    return value if value > 0 else 50.0


def vllm_max_attempts() -> int:
    """Self-correcting re-prompts against vLLM before failing over. Default 2.

    Lower than the OpenRouter client's 3, and the whole reason is the time
    budget. ``app/triage/routes.py`` allows ``REASONING_TIMEOUT_SECONDS``
    (150) for a turn. At two attempts the adapter can spend at most
    2 x :func:`vllm_timeout` = 100s, leaving room for the base model to
    answer inside the same turn. At three it could spend 150s alone and the
    fallback would never get to run — which is what turned a recoverable
    turn into a 504 measured at 119s on 2026-09-09.
    """
    raw = os.environ.get(VLLM_MAX_ATTEMPTS_ENV, "").strip()
    if not raw:
        return 2
    try:
        value = int(raw)
    except ValueError:
        return 2
    return value if value >= 1 else 2


def vllm_configured() -> bool:
    """Whether a vLLM endpoint has been named at all.

    Keyed on the URL being set explicitly rather than on
    :func:`vllm_url`, which has a localhost default — the fine-tuned model
    must not appear as a selectable option just because nothing was
    configured.
    """
    return bool(os.environ.get(VLLM_URL_ENV, "").strip())


def model_selector_enabled() -> bool:
    """Whether per-turn model choice is offered. Off unless asked for."""
    raw = os.environ.get(MODEL_SELECTOR_ENV, "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def cookie_secure() -> bool:
    """Whether auth cookies are marked ``Secure``. Off for local HTTP dev."""
    raw = os.environ.get(COOKIE_SECURE_ENV, "true").strip().lower()
    return raw not in {"0", "false", "no", "off"}


#: Cross-origin callers allowed to hit this API with credentials (cookies).
#: Empty by default — same-origin (the Next.js rewrite proxy) needs none of
#: this. Set when a frontend calls the API directly from a different origin
#: (a different host or port counts) — found necessary in dev because the
#: Next.js dev-server proxy does not reliably hold a slow upstream request
#: open (see docs/runbooks and app/triage/routes.py's own notes on this).
CORS_ORIGINS_ENV = "HERHEALTH_CORS_ORIGINS"


def cors_origins() -> list[str]:
    """Comma-separated origins from the environment, or an empty list.

    An empty list is not "allow nothing forever" as a hardcoded policy — it
    is "no direct cross-origin caller is configured", and
    ``CORSMiddleware`` with an empty ``allow_origins`` simply permits none,
    which is the correct default until a caller is named explicitly.
    """
    raw = os.environ.get(CORS_ORIGINS_ENV, "")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def google_client_id() -> str | None:
    """The OAuth client id Google ID tokens must be issued for, or ``None``
    if Google sign-in is not configured. Unlike :func:`database_url` and
    :func:`session_secret`, absence is not an error — Google sign-in is
    optional functionality no Google Cloud project has been provisioned for
    yet (unlike SES, which #6 already set up before #10 needed it). A
    process with this unset still boots; ``/accounts/sign-in/google``
    degrades to a clear "not configured" response instead.
    """
    return os.environ.get(GOOGLE_CLIENT_ID_ENV) or None
