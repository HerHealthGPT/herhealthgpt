"""The FastAPI dependency that turns an access-token cookie into a ``User``.

Reads and verifies the token only — no database lookup against ``sessions``,
because the access token is deliberately stateless (see ``tokens.py``). It
does still load the ``User`` row, since a caller needs more than an id (her
email, her verification state), and a user deleted mid-lifetime should stop
resolving even though her old access token has not technically expired.
"""

from __future__ import annotations

import uuid

from fastapi import Request
from sqlalchemy import select

from herhealth_backend.app.accounts.cookies import ACCESS_TOKEN_COOKIE
from herhealth_backend.app.accounts.errors import InvalidAccessToken
from herhealth_backend.app.accounts.models import User
from herhealth_backend.app.accounts.tokens import read_access_token
from herhealth_backend.app.db import Database

__all__ = ["get_current_user"]


async def get_current_user(request: Request) -> User:
    """The signed-in ``User``, resolved from the access-token cookie.

    Raises :class:`InvalidAccessToken` — not ``HTTPException`` directly — for
    a missing, invalid, or expired token, or one naming a user that no longer
    exists. ``error_handlers.py`` maps it to 401 in one place, so this
    dependency needs no knowledge of the HTTP status or wording involved.
    """
    token = request.cookies.get(ACCESS_TOKEN_COOKIE)
    if token is None:
        raise InvalidAccessToken()

    secret: str = request.app.state.session_secret
    try:
        user_id = uuid.UUID(read_access_token(secret, token))
    except ValueError as exc:
        raise InvalidAccessToken() from exc

    database: Database = request.app.state.database
    async with database.session() as session:
        user = await session.scalar(select(User).where(User.id == user_id))

    if user is None:
        raise InvalidAccessToken()
    return user
