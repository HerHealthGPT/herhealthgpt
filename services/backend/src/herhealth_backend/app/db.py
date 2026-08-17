"""The application's connection to PostgreSQL.

:class:`Database` owns the async engine and hands out sessions. It is created
once at start-up and disposed at shutdown, so the connection pool lives for the
life of the process rather than per request.

Two things are deliberately small here. :meth:`Database.ping` does the least a
real round-trip can — ``SELECT 1`` — because the health check needs to prove the
database answers, not that a table exists. And :meth:`Database.session` yields a
session and nothing more; the domain work that fills those sessions with users
and conversations arrives in later tickets, against this same seam.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

__all__ = ["Database"]


class Database:
    """An async engine and session factory for one PostgreSQL database."""

    def __init__(self, url: str) -> None:
        self._engine: AsyncEngine = create_async_engine(url, pool_pre_ping=True)
        self._sessionmaker: async_sessionmaker[AsyncSession] = async_sessionmaker(
            self._engine, expire_on_commit=False
        )

    @property
    def engine(self) -> AsyncEngine:
        return self._engine

    async def ping(self) -> None:
        """Do a real query, so a reachable pool but a dead database still fails.

        Raises :class:`sqlalchemy.exc.SQLAlchemyError` (or a driver error) when
        the database cannot be reached or will not answer. Callers turn that into
        a 503; nothing here swallows it.
        """
        async with self._engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """A session that is closed when the block ends, whatever happens in it."""
        async with self._sessionmaker() as session:
            yield session

    async def dispose(self) -> None:
        """Close the connection pool. Called once, at shutdown."""
        await self._engine.dispose()
