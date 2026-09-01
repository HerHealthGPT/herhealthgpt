"""Slowing down repeated requests for a fresh verification code (#10).

Mirrors ``sign_in_throttle.py`` exactly, for the same reasons: keyed on the
normalised email alone (never a user id, so an address with no account
throttles identically to one with a real, unverified account — the counter
itself must not become a way to learn which addresses are registered), and a
plain time-windowed count rather than anything that needs a cleanup job.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from herhealth_backend.app.accounts.models import VerificationCodeSend

__all__ = ["MAX_SENDS", "SEND_WINDOW", "is_send_locked_out", "record_send"]

#: Codes sent to one address within SEND_WINDOW before further requests are blocked.
MAX_SENDS = 3

#: How far back a send still counts. A lockout lifts on its own once every
#: counted send has aged out.
SEND_WINDOW = timedelta(minutes=15)


async def is_send_locked_out(session: AsyncSession, email: str) -> bool:
    """Whether ``email`` has been sent MAX_SENDS codes within SEND_WINDOW."""
    cutoff = datetime.now(UTC) - SEND_WINDOW
    count = await session.scalar(
        select(func.count())
        .select_from(VerificationCodeSend)
        .where(VerificationCodeSend.email == email, VerificationCodeSend.created_at >= cutoff)
    )
    return (count or 0) >= MAX_SENDS


async def record_send(session: AsyncSession, email: str) -> None:
    """Record that a code was sent to ``email``. Caller commits."""
    session.add(VerificationCodeSend(email=email))
