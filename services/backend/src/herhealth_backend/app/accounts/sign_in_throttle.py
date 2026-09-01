"""Slowing down repeated failed sign-ins for one address (#9).

A woman guessing at her own password gets a handful of tries; a script
guessing at everyone's addresses does not. Keyed on the normalised email
alone, never the caller's IP: an IP is cheap to rotate, this project has no
reverse proxy recording a trustworthy one yet, and a per-address counter is
what "repeated failed sign-in attempts for one address" (the acceptance
criterion) actually asks for. Counting the same way for an address that has
no account as for one that does is what keeps this mechanism from becoming a
second oracle for "does this address exist" alongside sign_in.py's.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from herhealth_backend.app.accounts.models import SignInFailure

__all__ = ["MAX_FAILURES", "LOCKOUT_WINDOW", "is_locked_out", "record_failure", "clear_failures"]

#: Failures within LOCKOUT_WINDOW before further attempts for that address are blocked.
MAX_FAILURES = 5

#: How far back a failure still counts. A lockout lifts on its own once every
#: counted failure has aged out, with nothing to run on a timer.
LOCKOUT_WINDOW = timedelta(minutes=15)


async def is_locked_out(session: AsyncSession, email: str) -> bool:
    """Whether ``email`` has failed sign-in MAX_FAILURES times within LOCKOUT_WINDOW."""
    cutoff = datetime.now(UTC) - LOCKOUT_WINDOW
    count = await session.scalar(
        select(func.count())
        .select_from(SignInFailure)
        .where(SignInFailure.email == email, SignInFailure.created_at >= cutoff)
    )
    return (count or 0) >= MAX_FAILURES


async def record_failure(session: AsyncSession, email: str) -> None:
    """Record one failed sign-in attempt against ``email``. Caller commits."""
    session.add(SignInFailure(email=email))


async def clear_failures(session: AsyncSession, email: str) -> None:
    """Forget ``email``'s failure history, on a successful sign-in. Caller commits."""
    await session.execute(delete(SignInFailure).where(SignInFailure.email == email))
