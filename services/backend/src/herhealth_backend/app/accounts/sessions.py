"""The Sessions use cases: starting one, exchanging its refresh token, ending it.

A session is a database row plus a refresh token the row never stores
directly — only ``tokens.hash_refresh_token``'s digest of it. The access
token handed back alongside it is not tracked anywhere at all; see
``tokens.py`` for why that is fine.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import ColumnElement, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from herhealth_backend.app.accounts.errors import InvalidSession
from herhealth_backend.app.accounts.models import Session, User
from herhealth_backend.app.accounts.session_policy import IDLE_TIMEOUT, REFRESH_TOKEN_TTL
from herhealth_backend.app.accounts.tokens import (
    generate_refresh_token,
    hash_refresh_token,
    issue_access_token,
)

__all__ = [
    "start_session",
    "get_active_session",
    "refresh_session",
    "end_session",
    "end_all_sessions",
]


async def start_session(session: AsyncSession, secret: str, user: User) -> tuple[str, str]:
    """Create a session row for ``user``. Returns ``(access_token, refresh_token)``.

    Caller commits — this only adds to the session, matching registration.py's
    pattern of leaving the transaction boundary to the use case that orchestrates.
    """
    raw_refresh_token = generate_refresh_token()
    now = datetime.now(UTC)
    session.add(
        Session(
            user_id=user.id,
            refresh_token_hash=hash_refresh_token(raw_refresh_token),
            last_used_at=now,
            expires_at=now + REFRESH_TOKEN_TTL,
        )
    )
    access_token = issue_access_token(secret, user_id=str(user.id))
    return access_token, raw_refresh_token


async def get_active_session(session: AsyncSession, raw_refresh_token: str) -> Session:
    """The session ``raw_refresh_token`` belongs to, if it is still usable.

    Used both by :func:`refresh_session` and directly by routes that need to
    know *whose* session this is (sign-out-everywhere) without minting a new
    access token. Raises :class:`InvalidSession` for a token that is missing,
    unknown, revoked, past its absolute lifetime, or idle too long — never
    distinguishing which.
    """
    row = await session.scalar(
        select(Session).where(Session.refresh_token_hash == hash_refresh_token(raw_refresh_token))
    )
    now = datetime.now(UTC)
    if (
        row is None
        or row.revoked_at is not None
        or row.expires_at <= now
        or (now - row.last_used_at) > IDLE_TIMEOUT
    ):
        raise InvalidSession()
    return row


async def refresh_session(session: AsyncSession, secret: str, raw_refresh_token: str) -> str:
    """Exchange a still-valid refresh token for a new access token.

    Also counts as activity: touches ``last_used_at``, so IDLE_TIMEOUT is
    measured from the most recent refresh, not from when the session first
    started. Raises InvalidSession the same way :func:`get_active_session`
    does. Caller commits.
    """
    row = await get_active_session(session, raw_refresh_token)
    row.last_used_at = datetime.now(UTC)
    return issue_access_token(secret, user_id=str(row.user_id))


async def _revoke(session: AsyncSession, *predicates: ColumnElement[bool]) -> None:
    await session.execute(
        update(Session).where(*predicates).values(revoked_at=datetime.now(UTC))
    )


async def end_session(session: AsyncSession, raw_refresh_token: str) -> None:
    """Revoke the session ``raw_refresh_token`` belongs to.

    Never raises for a token that is already invalid, unknown, or already
    revoked — signing out ends the same way regardless: no active session left
    for it. Caller commits.
    """
    await _revoke(
        session,
        Session.refresh_token_hash == hash_refresh_token(raw_refresh_token),
        Session.revoked_at.is_(None),
    )


async def end_all_sessions(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Revoke every active session belonging to ``user_id``.

    New access tokens stop being mintable immediately. Access tokens already
    issued keep working until their own short lifetime runs out — the
    tradeoff CONTEXT.md accepted in making access tokens unrevocable. Caller
    commits.
    """
    await _revoke(session, Session.user_id == user_id, Session.revoked_at.is_(None))
