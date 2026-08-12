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

__all__ = ["DATABASE_URL_ENV", "database_url"]

#: The one environment variable the process reads to find its database. Namespaced
#: so it cannot collide with a bare ``DATABASE_URL`` some other tool sets.
DATABASE_URL_ENV = "HERHEALTH_DATABASE_URL"


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
