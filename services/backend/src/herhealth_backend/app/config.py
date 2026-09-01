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
