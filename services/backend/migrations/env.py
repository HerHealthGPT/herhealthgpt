"""Alembic's entry point, run whenever migrations are applied.

Synchronous on purpose. Migrations run rarely and briefly — at deploy time and
at the start of a test session — so there is nothing to gain from the async
engine the application uses, and a sync flow is far easier to read. psycopg 3
backs both, so the same URL works here and in the app.

Users and credentials arrived with #8, sessions and sign-in failures with #9,
email verification codes and sends with #10, Google credentials with #11.
Triage's consultation sessions and messages (issue #20 item 6) arrived as a
second, separate declarative base — CONTEXT-MAP.md's Triage/Accounts split,
carried into the ORM. Autogenerate needs to see both, so ``target_metadata``
below is a list rather than one module's ``Base.metadata``; Alembic accepts
either.
"""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from herhealth_backend.app.accounts.models import Base as AccountsBase
from herhealth_backend.app.triage.models import Base as TriageBase

config = context.config

if config.config_file_name is not None:
    # disable_existing_loggers defaults to True, which silently disables any
    # logger that already exists and isn't one of alembic.ini's own three
    # (root, sqlalchemy, alembic) — including the app's own module loggers
    # (email_sender.py's, for one), if this runs in the same process after
    # they were created. Only the test harness runs migrations in-process
    # (a real deploy runs `alembic upgrade` as its own process), but that is
    # exactly where the app's logging then goes silently, permanently dark
    # for the rest of the session.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = [AccountsBase.metadata, TriageBase.metadata]


def _database_url() -> str:
    """Where to migrate.

    The test harness sets ``sqlalchemy.url`` on the config to point at its
    throwaway container. A plain ``alembic upgrade`` from the command line has no
    such config, so it falls back to the same ``HERHEALTH_DATABASE_URL`` the
    application reads — one variable, one database, for both.
    """
    url = config.get_main_option("sqlalchemy.url")
    if not url:
        url = os.environ.get("HERHEALTH_DATABASE_URL")
    if not url:
        raise RuntimeError(
            "No database URL. Set HERHEALTH_DATABASE_URL, or pass sqlalchemy.url "
            "on the Alembic config (the test harness does the latter)."
        )
    return url


def run_migrations_offline() -> None:
    """Emit SQL against a URL without a live connection (``alembic upgrade --sql``)."""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Apply migrations over a real connection."""
    connectable = create_engine(_database_url(), poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
