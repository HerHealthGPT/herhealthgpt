"""Profile fields a signed-in user may edit herself."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from herhealth_backend.app.accounts.errors import (
    InvalidDateOfBirth,
    InvalidDisplayName,
    InvalidHealthNote,
    InvalidSession,
)
from herhealth_backend.app.accounts.models import HealthNote, User

# Accounts is allowed to depend on Triage, never the reverse — CONTEXT-MAP.md.
from herhealth_backend.triage.age_bands import age_in_years

__all__ = [
    "MAX_AGE_YEARS",
    "MAX_HEALTH_NOTE_LENGTH",
    "MIN_AGE_YEARS",
    "clear_health_note",
    "health_note_for",
    "normalize_display_name",
    "normalize_health_note",
    "update_date_of_birth",
    "update_display_name",
    "update_health_note",
    "validate_date_of_birth",
]

_MAX_DISPLAY_NAME_LENGTH = 80

#: Below this, we do not accept an account's date of birth. Not a clinical
#: judgement about who has periods — ``features.yaml``'s ``under_20`` band
#: exists precisely because young users are in scope — but the ordinary floor
#: for someone agreeing to a service's terms on her own behalf.
MIN_AGE_YEARS = 13

#: Above this, the date is a typo rather than a person. Catches a mistyped
#: year (1902 for 1992) that would otherwise silently land her in ``55_plus``.
MAX_AGE_YEARS = 120

#: Long enough for a real paragraph about her health, short enough that this
#: cannot be used as free storage. She is told the limit before she hits it.
MAX_HEALTH_NOTE_LENGTH = 2000


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


def validate_date_of_birth(value: date, *, today: date) -> date:
    """Return ``value`` if it could plausibly be a living user's birth date.

    ``today`` is passed in rather than read from the clock for the same
    reason ``triage.age_bands`` does it: a test about the day someone turns
    13 has to be able to name that day.

    Raises :class:`InvalidDateOfBirth` for a future date or an implausible
    age. Deliberately not silently corrected — a date we cannot believe is
    not a date to guess at, and age feeds a band that changes what the
    system suspects.
    """
    if value > today:
        raise InvalidDateOfBirth()
    age = age_in_years(value, today=today)
    if age < MIN_AGE_YEARS or age > MAX_AGE_YEARS:
        raise InvalidDateOfBirth()
    return value


def normalize_health_note(value: str | None) -> str | None:
    """Trim. ``None`` or blank means "no note", which clears any stored one.

    Interior whitespace and newlines are preserved, unlike a display name:
    she may reasonably type a list, and reflowing her own words into one line
    would be us editing what she told us.
    """
    if value is None:
        return None
    trimmed = value.strip()
    if not trimmed:
        return None
    if len(trimmed) > MAX_HEALTH_NOTE_LENGTH:
        raise InvalidHealthNote()
    return trimmed


async def _load_user(session: AsyncSession, user_id: uuid.UUID) -> User:
    """The authenticated user, or raise.

    ``InvalidSession`` rather than a not-found: the caller authenticated
    moments ago, so a missing row means her account was deleted mid-request,
    and "not signed in" is then the honest answer.
    """
    user = await session.get(User, user_id)
    if user is None:
        raise InvalidSession()
    return user


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


async def update_date_of_birth(
    session: AsyncSession, user_id: uuid.UUID, *, date_of_birth: date, today: date
) -> User:
    """Set her date of birth. There is no "clear it" path on purpose.

    Every new sign-up supplies one, and a user who already has one has no
    reason to erase it — no stored age means the system asks her again every
    consultation, which is the cost this field exists to remove.
    """
    user = await _load_user(session, user_id)
    user.date_of_birth = validate_date_of_birth(date_of_birth, today=today)
    await session.commit()
    await session.refresh(user)
    return user


async def health_note_for(session: AsyncSession, user_id: uuid.UUID) -> HealthNote | None:
    """Her note, or ``None``. Queried by ``user_id``, which is unique on the
    table — the primary key is the row's own id and is never known here."""
    return await session.scalar(select(HealthNote).where(HealthNote.user_id == user_id))


async def update_health_note(
    session: AsyncSession, user_id: uuid.UUID, *, content: str | None
) -> str | None:
    """Write, replace or clear her note. Returns what is now stored.

    Blank content deletes the row rather than storing an empty string, so
    "she has told us nothing" has exactly one representation in the database
    instead of two that read the same to a person and differently to code.
    """
    normalized = normalize_health_note(content)
    if normalized is None:
        await clear_health_note(session, user_id)
        return None

    await _load_user(session, user_id)
    existing = await health_note_for(session, user_id)
    if existing is None:
        session.add(HealthNote(user_id=user_id, content=normalized))
    else:
        existing.content = normalized
    await session.commit()
    return normalized


async def clear_health_note(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Delete her note if there is one. Idempotent."""
    existing = await health_note_for(session, user_id)
    if existing is not None:
        await session.delete(existing)
        await session.commit()
