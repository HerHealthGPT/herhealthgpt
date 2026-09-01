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
