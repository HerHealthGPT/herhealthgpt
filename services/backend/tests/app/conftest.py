"""Fixtures for the app tests: a real PostgreSQL, migrated once, isolated per test.

The container starts once for the whole session (it is slow to start and there
is nothing test-specific about it), migrations run against it once, and then each
test gets a connection wrapped in a transaction that is rolled back when the test
ends. Tests therefore never see each other's rows, and the suite leaves no state
behind — all without a per-test database.

Nothing here reaches a network or a cloud account: testcontainers pulls a public
postgres image and runs it in local Docker. The triage suite imports none of
this, so it still runs with Docker absent.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

# Ryuk is testcontainers' reaper container; its port mapping is unreliable on
# Docker for Windows, and the `with PostgresContainer(...)` block below stops the
# database itself, so the reaper buys us nothing here. Set before the import that
# reads it.
os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")

# Give psycopg a loop it can drive on Windows, before pytest-asyncio builds one.
from herhealth_backend.app.eventloop import use_selector_loop_on_windows  # noqa: E402

use_selector_loop_on_windows()

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    create_async_engine,
)
from testcontainers.community.postgres import PostgresContainer  # noqa: E402

from herhealth_backend.app import Database, create_app  # noqa: E402
from herhealth_backend.app.accounts.errors import GoogleTokenInvalid  # noqa: E402
from herhealth_backend.app.accounts.google_identity import GoogleIdentity  # noqa: E402
from herhealth_backend.app.accounts.stored_files import FileStore  # noqa: E402

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_ALEMBIC_INI = _BACKEND_ROOT / "alembic.ini"

#: Not a real secret — only ever used to sign tokens inside this test process.
_TEST_SESSION_SECRET = "test-only-session-secret-do-not-use-in-production"


class RecordingEmailSender:
    """An :class:`~herhealth_backend.app.accounts.email_sender.EmailSender`
    that remembers what it was asked to send, so a test can read the code a
    route handed it instead of parsing ``ConsoleEmailSender``'s log output.
    Used everywhere in this suite instead of ``SesEmailSender`` — #10's own
    requirement that the suite run with no network and no provider account.

    Verification and password-reset codes are recorded separately (#12) —
    both are 6-digit codes and a test asking for the wrong kind by mistake
    should fail loudly rather than silently reading the other flow's code.
    """

    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []
        self.password_reset_sent: list[tuple[str, str]] = []

    async def send_verification_code(self, *, to: str, code: str) -> None:
        self.sent.append((to, code))

    async def send_password_reset_code(self, *, to: str, code: str) -> None:
        self.password_reset_sent.append((to, code))

    def code_for(self, to: str) -> str:
        """The most recent verification code sent to ``to``. Raises if none was."""
        for recipient, code in reversed(self.sent):
            if recipient == to:
                return code
        raise AssertionError(f"No verification code was sent to {to!r}")

    def password_reset_code_for(self, to: str) -> str:
        """The most recent password-reset code sent to ``to``. Raises if none was."""
        for recipient, code in reversed(self.password_reset_sent):
            if recipient == to:
                return code
        raise AssertionError(f"No password reset code was sent to {to!r}")


class StaticGoogleTokenVerifier:
    """A :class:`~herhealth_backend.app.accounts.google_identity.GoogleTokenVerifier`
    that returns a fixed identity regardless of the token string, or raises
    :class:`GoogleTokenInvalid` if none was configured — #11's own
    requirement that tests supply identities directly with no network call.
    """

    def __init__(self, identity: GoogleIdentity | None = None) -> None:
        self.identity = identity

    async def verify(self, id_token: str) -> GoogleIdentity:
        if self.identity is None:
            raise GoogleTokenInvalid()
        return self.identity


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    """A migrated PostgreSQL for the session; yields its SQLAlchemy URL.

    The ``psycopg`` driver marker gives a URL that works for both the sync engine
    Alembic uses and the async engine the app uses.
    """
    with PostgresContainer("postgres:16-alpine", driver="psycopg") as postgres:
        url = postgres.get_connection_url()
        config = Config(str(_ALEMBIC_INI))
        config.set_main_option("script_location", str(_BACKEND_ROOT / "migrations"))
        config.set_main_option("sqlalchemy.url", url)
        command.upgrade(config, "head")
        yield url


@pytest_asyncio.fixture
async def engine(database_url: str) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(database_url)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def connection(engine: AsyncEngine) -> AsyncIterator[AsyncConnection]:
    """A connection inside a transaction that is always rolled back."""
    async with engine.connect() as connection:
        transaction = await connection.begin()
        try:
            yield connection
        finally:
            await transaction.rollback()


@pytest_asyncio.fixture
async def db_session(connection: AsyncConnection) -> AsyncIterator[AsyncSession]:
    """A session bound to the rolled-back connection.

    ``create_savepoint`` mode lets the session commit and roll back within the
    outer transaction without ending it, so code under test can use ``commit()``
    normally while the fixture still discards everything at the end.

    ``expire_on_commit=False`` matches ``Database``'s real session factory
    (``app/db.py``) — without it, an object a test holds across a second
    ``commit()`` (e.g. a ``User`` returned by one use case, then passed into
    another) has its attributes expire, and accessing one outside SQLAlchemy's
    async greenlet raises ``MissingGreenlet`` rather than a useful test failure.
    """
    session = AsyncSession(
        bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
    )
    try:
        yield session
    finally:
        await session.close()


@pytest.fixture
def email_sender() -> RecordingEmailSender:
    """A fresh recording sender per test, so nothing sent in one test is
    visible to the next."""
    return RecordingEmailSender()


@pytest.fixture
def google_verifier() -> StaticGoogleTokenVerifier:
    """No identity configured by default — a test sets ``.identity`` to
    whatever ``GoogleIdentity`` its scenario needs."""
    return StaticGoogleTokenVerifier()


@pytest.fixture
def file_store(tmp_path: Path) -> FileStore:
    """Kept files go to a fresh directory per test (ADR 0020)."""
    return FileStore(tmp_path / "uploads")


@pytest_asyncio.fixture
async def client(
    database_url: str,
    email_sender: RecordingEmailSender,
    google_verifier: StaticGoogleTokenVerifier,
    file_store: FileStore,
) -> AsyncIterator[AsyncClient]:
    """An ASGI-driven HTTP client against a real app, pointed at the migrated database.

    Uses its own connection pool rather than the ``db_session`` fixture's
    rolled-back transaction, so a test using ``client`` sees whatever a
    previous ``client`` test committed. Route tests that need isolation from
    each other should use distinct email addresses, the way the rest of this
    suite avoids colliding table names.

    ``base_url`` is ``https://`` — no TLS is actually involved with
    ``ASGITransport``, but the auth cookies (see ``accounts/cookies.py``) are
    marked ``Secure``, and httpx's cookie jar (like a real browser) refuses to
    replay a ``Secure`` cookie back on a request it thinks is plain HTTP.
    """
    database = Database(database_url)
    app = create_app(
        database=database,
        session_secret=_TEST_SESSION_SECRET,
        email_sender=email_sender,
        google_verifier=google_verifier,
        file_store=file_store,
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://test") as client:
        yield client
    await database.dispose()
