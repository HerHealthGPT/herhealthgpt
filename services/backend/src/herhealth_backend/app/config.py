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
    "OPENROUTER_API_KEY_ENV",
    "openrouter_api_key",
    "TRIAGE_MODE_ENV",
    "triage_mode",
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
#: OPENROUTER_API_KEY and a running services/model. ``off`` disables triage.
TRIAGE_MODE_ENV = "HERHEALTH_TRIAGE_MODE"

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
    """``demo``, ``openrouter``, or ``off``. Defaults to ``openrouter`` when a
    key is set, otherwise ``off``. Set ``HERHEALTH_TRIAGE_MODE=demo`` explicitly
    for local MVP testing without OpenRouter or services/model.
    """
    explicit = os.environ.get(TRIAGE_MODE_ENV, "").strip().lower()
    if explicit in {"demo", "openrouter", "off"}:
        return explicit
    if openrouter_api_key():
        return "openrouter"
    return "off"


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
