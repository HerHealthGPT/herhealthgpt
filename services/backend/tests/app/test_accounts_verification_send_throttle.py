"""``verification_send_throttle`` against a real (rolled-back) PostgreSQL transaction."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from herhealth_backend.app.accounts.verification_send_throttle import (
    MAX_SENDS,
    is_send_locked_out,
    record_send,
)


async def test_is_send_locked_out_is_false_with_no_sends(db_session: AsyncSession) -> None:
    assert await is_send_locked_out(db_session, "woman@example.com") is False


async def test_is_send_locked_out_becomes_true_at_max_sends(db_session: AsyncSession) -> None:
    for _ in range(MAX_SENDS - 1):
        await record_send(db_session, "woman@example.com")
    await db_session.flush()
    assert await is_send_locked_out(db_session, "woman@example.com") is False

    await record_send(db_session, "woman@example.com")
    await db_session.flush()
    assert await is_send_locked_out(db_session, "woman@example.com") is True


async def test_sends_are_scoped_to_one_address(db_session: AsyncSession) -> None:
    for _ in range(MAX_SENDS):
        await record_send(db_session, "woman@example.com")
    await db_session.flush()

    assert await is_send_locked_out(db_session, "other-woman@example.com") is False
