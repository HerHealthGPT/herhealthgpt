"""Serializing a decision, per email address, with a Postgres advisory lock.

The recurring shape this closes: a check (a SELECT counting recent
failures/sends) and a write (an INSERT recording this attempt) are not
atomic with each other, so under READ COMMITTED, concurrent requests for the
same address can each read the count before any of the others' inserts
commit — every one of them passes the check, and a limit meant to allow only
a handful of attempts lets through as many as arrived in the same instant.
``pg_advisory_xact_lock`` serializes the whole check-then-write decision
instead, and releases itself automatically at commit or rollback.

``namespace`` keeps unrelated call sites (sign-in, email verification, a
future password-reset throttle) from contending over an address that
happens to be attempting more than one of them at once — but it is mixed
into one hashed key, not a genuinely separate lock space.
``pg_advisory_xact_lock``'s single-bigint form hashes its whole input to one
64-bit key, so two different ``(namespace, email)`` inputs can, with a
hashtext()-sized (32-bit) probability, still collide onto the same lock.
That is the same accepted risk sign_in.py's throttle already carried before
this module existed — over-serializing two unrelated decisions, never
under-protecting either one — not a new one introduced by sharing it.

Deliberately never held across slow work (argon2id, a network email send):
doing so turns a fix for a counting race into a lever anyone can pull to
delay a *legitimate* concurrent request for the same address.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

__all__ = ["serialize_per_email"]


async def serialize_per_email(session: AsyncSession, namespace: str, email: str) -> None:
    """Block until no other in-flight decision for ``(namespace, email)`` holds this lock."""
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:namespace || ':' || :email))"),
        {"namespace": namespace, "email": email},
    )
