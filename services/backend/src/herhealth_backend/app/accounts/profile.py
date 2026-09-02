"""Profile fields a signed-in user may edit herself."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from herhealth_backend.app.accounts.errors import InvalidDisplayName
from herhealth_backend.app.accounts.models import User

__all__ = ["normalize_display_name", "update_display_name"]

_MAX_DISPLAY_NAME_LENGTH = 80


def normalize_display_name(value: str | None) -> str | None:
    """Trim and collapse whitespace. Empty input clears the stored name."""
    if value is None:
        return None
    trimmed = " ".join(value.strip().split())
    if not trimmed:
        return None
    if len(trimmed) > _MAX_DISPLAY_NAME_LENGTH:
        raise InvalidDisplayName()
    return trimmed


async def update_display_name(
    session: AsyncSession, user_id: uuid.UUID, *, display_name: str | None
) -> User:
    user = await session.get(User, user_id)
    if user is None:
        raise InvalidDisplayName()
    user.display_name = normalize_display_name(display_name)
    await session.commit()
    await session.refresh(user)
    return user
