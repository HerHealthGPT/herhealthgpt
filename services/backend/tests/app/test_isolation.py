"""Proof that the per-test transaction really is rolled back.

Both tests do the same thing to the same table name, in whatever order pytest
runs them: create a scratch table, insert one tagged row, and assert the table
holds exactly that one row. If a test's transaction leaked past its end, the
second test to run would either find the other's row (count 2) or the table
already populated — so the pair passing is the isolation guarantee, not a
coincidence. The table is never committed and never migrated; it exists only
inside each rolled-back transaction.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def _probe_with(session: AsyncSession, tag: str) -> None:
    await session.execute(text("CREATE TABLE IF NOT EXISTS isolation_probe (tag text)"))
    await session.execute(
        text("INSERT INTO isolation_probe (tag) VALUES (:tag)"), {"tag": tag}
    )
    count = await session.scalar(text("SELECT count(*) FROM isolation_probe"))
    assert count == 1, "another test's rows leaked into this transaction"


async def test_transaction_is_isolated_alpha(db_session: AsyncSession) -> None:
    await _probe_with(db_session, "alpha")


async def test_transaction_is_isolated_beta(db_session: AsyncSession) -> None:
    await _probe_with(db_session, "beta")
