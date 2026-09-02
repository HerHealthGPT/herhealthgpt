"""Delete a user and every row that references her.

Issue #14: immediate, cascading, no soft-delete. Rows keyed only by email
(``SignInFailure``, ``VerificationCodeSend``, ``PasswordResetSend``) have no
foreign key to ``users`` and are removed explicitly before the user row goes.
Everything else falls to ``ON DELETE CASCADE`` — credentials, auth sessions,
verification and reset codes, consultation sessions, and their messages.
"""

from __future__ import annotations

import uuid

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from herhealth_backend.app.accounts.models import (
    PasswordResetSend,
    SignInFailure,
    User,
    VerificationCodeSend,
)

__all__ = ["delete_user_account"]


async def delete_user_account(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Remove ``user_id`` and all data tied to her. Caller commits."""
    user = await session.get(User, user_id)
    if user is None:
        return

    email = user.email

    await session.execute(delete(SignInFailure).where(SignInFailure.email == email))
    await session.execute(
        delete(VerificationCodeSend).where(VerificationCodeSend.email == email)
    )
    await session.execute(delete(PasswordResetSend).where(PasswordResetSend.email == email))

    await session.delete(user)
