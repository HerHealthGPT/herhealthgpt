"""``sessions.py`` use cases against a real (rolled-back) PostgreSQL transaction."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from herhealth_backend.app.accounts.errors import InvalidSession
from herhealth_backend.app.accounts.models import Session
from herhealth_backend.app.accounts.registration import register_user
from herhealth_backend.app.accounts.sessions import (
    end_all_sessions,
    end_session,
    refresh_session,
    start_session,
)
from herhealth_backend.app.accounts.tokens import read_access_token

_SECRET = "unit-test-secret"


async def _a_user(db_session: AsyncSession):
    return await register_user(db_session, email="woman@example.com", password="correcthorse1")


async def test_start_session_returns_tokens_identifying_the_user(
    db_session: AsyncSession,
) -> None:
    user = await _a_user(db_session)

    access_token, refresh_token = await start_session(db_session, _SECRET, user)
    await db_session.commit()

    assert read_access_token(_SECRET, access_token) == str(user.id)
    assert refresh_token

    row = await db_session.scalar(select(Session).where(Session.user_id == user.id))
    assert row is not None
    assert row.revoked_at is None


async def test_refresh_session_returns_a_new_access_token_for_the_same_user(
    db_session: AsyncSession,
) -> None:
    user = await _a_user(db_session)
    _, refresh_token = await start_session(db_session, _SECRET, user)
    await db_session.commit()

    new_access_token = await refresh_session(db_session, _SECRET, refresh_token)

    assert read_access_token(_SECRET, new_access_token) == str(user.id)


async def test_refresh_session_touches_last_used_at(db_session: AsyncSession) -> None:
    user = await _a_user(db_session)
    _, refresh_token = await start_session(db_session, _SECRET, user)
    await db_session.commit()
    row = await db_session.scalar(select(Session).where(Session.user_id == user.id))
    assert row is not None
    row.last_used_at = datetime.now(UTC) - timedelta(days=1)
    await db_session.commit()

    before = row.last_used_at
    await refresh_session(db_session, _SECRET, refresh_token)

    assert row.last_used_at > before


async def test_refresh_session_rejects_an_unknown_token(db_session: AsyncSession) -> None:
    with pytest.raises(InvalidSession):
        await refresh_session(db_session, _SECRET, "not-a-real-refresh-token")


async def test_refresh_session_rejects_a_revoked_session(db_session: AsyncSession) -> None:
    user = await _a_user(db_session)
    _, refresh_token = await start_session(db_session, _SECRET, user)
    await db_session.commit()
    await end_session(db_session, refresh_token)
    await db_session.commit()

    with pytest.raises(InvalidSession):
        await refresh_session(db_session, _SECRET, refresh_token)


async def test_refresh_session_rejects_a_session_past_its_absolute_lifetime(
    db_session: AsyncSession,
) -> None:
    user = await _a_user(db_session)
    _, refresh_token = await start_session(db_session, _SECRET, user)
    await db_session.commit()
    row = await db_session.scalar(select(Session).where(Session.user_id == user.id))
    assert row is not None
    row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await db_session.commit()

    with pytest.raises(InvalidSession):
        await refresh_session(db_session, _SECRET, refresh_token)


async def test_refresh_session_rejects_a_session_left_idle_too_long(
    db_session: AsyncSession,
) -> None:
    user = await _a_user(db_session)
    _, refresh_token = await start_session(db_session, _SECRET, user)
    await db_session.commit()
    row = await db_session.scalar(select(Session).where(Session.user_id == user.id))
    assert row is not None
    row.last_used_at = datetime.now(UTC) - timedelta(days=365)
    await db_session.commit()

    with pytest.raises(InvalidSession):
        await refresh_session(db_session, _SECRET, refresh_token)


async def test_end_session_revokes_only_that_session(db_session: AsyncSession) -> None:
    user = await _a_user(db_session)
    _, token_a = await start_session(db_session, _SECRET, user)
    _, token_b = await start_session(db_session, _SECRET, user)
    await db_session.commit()

    await end_session(db_session, token_a)
    await db_session.commit()

    with pytest.raises(InvalidSession):
        await refresh_session(db_session, _SECRET, token_a)
    # The other session is untouched.
    await refresh_session(db_session, _SECRET, token_b)


async def test_end_session_on_an_unknown_token_does_not_raise(db_session: AsyncSession) -> None:
    await end_session(db_session, "not-a-real-refresh-token")
    await db_session.commit()


async def test_end_all_sessions_revokes_every_session_for_the_user(
    db_session: AsyncSession,
) -> None:
    user = await _a_user(db_session)
    _, token_a = await start_session(db_session, _SECRET, user)
    _, token_b = await start_session(db_session, _SECRET, user)
    await db_session.commit()

    await end_all_sessions(db_session, user.id)
    await db_session.commit()

    with pytest.raises(InvalidSession):
        await refresh_session(db_session, _SECRET, token_a)
    with pytest.raises(InvalidSession):
        await refresh_session(db_session, _SECRET, token_b)


async def test_end_all_sessions_does_not_touch_another_users_sessions(
    db_session: AsyncSession,
) -> None:
    user_a = await _a_user(db_session)
    user_b = await register_user(db_session, email="other@example.com", password="correcthorse1")
    _, token_a = await start_session(db_session, _SECRET, user_a)
    _, token_b = await start_session(db_session, _SECRET, user_b)
    await db_session.commit()

    await end_all_sessions(db_session, user_a.id)
    await db_session.commit()

    with pytest.raises(InvalidSession):
        await refresh_session(db_session, _SECRET, token_a)
    await refresh_session(db_session, _SECRET, token_b)
