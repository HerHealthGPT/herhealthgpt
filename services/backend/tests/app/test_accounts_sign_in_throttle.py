"""``sign_in_throttle`` against a real (rolled-back) PostgreSQL transaction."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from herhealth_backend.app.accounts.sign_in_throttle import (
    MAX_FAILURES,
    clear_failures,
    is_locked_out,
    record_failure,
)


async def test_is_locked_out_is_false_with_no_failures(db_session: AsyncSession) -> None:
    assert await is_locked_out(db_session, "woman@example.com") is False


async def test_is_locked_out_becomes_true_at_max_failures(db_session: AsyncSession) -> None:
    for _ in range(MAX_FAILURES - 1):
        await record_failure(db_session, "woman@example.com")
    await db_session.flush()
    assert await is_locked_out(db_session, "woman@example.com") is False

    await record_failure(db_session, "woman@example.com")
    await db_session.flush()
    assert await is_locked_out(db_session, "woman@example.com") is True


async def test_failures_are_scoped_to_one_address(db_session: AsyncSession) -> None:
    for _ in range(MAX_FAILURES):
        await record_failure(db_session, "woman@example.com")
    await db_session.flush()

    assert await is_locked_out(db_session, "other-woman@example.com") is False


async def test_clear_failures_lifts_a_lockout(db_session: AsyncSession) -> None:
    for _ in range(MAX_FAILURES):
        await record_failure(db_session, "woman@example.com")
    await db_session.flush()
    assert await is_locked_out(db_session, "woman@example.com") is True

    await clear_failures(db_session, "woman@example.com")

    assert await is_locked_out(db_session, "woman@example.com") is False
