"""The email verification use cases: issuing a code, checking one, resending.

Sending a code is deliberately not part of ``registration.py``'s
``register_user`` — the same reasoning that function's own docstring already
gives for not signing her in: each use case does one thing, so it can be
tested without the others. ``routes.py`` orchestrates ``register_user`` then
:func:`send_verification_code` for the ``/accounts/register`` endpoint.

All three public functions here take the same ``advisory_lock`` mutex, keyed
on the address, as their first move — not because each individually needs
it (the throttle race only touches ``request_verification_resend``, the
attempts race only touches ``verify_email``), but because they read and
write the *same* row, and locking only some of the functions that touch it
still lets the others interleave with whichever one is locked. One mutex
over the whole subsystem's per-email state is simpler to reason about than
three narrower locks each proven safe only against the others.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from herhealth_backend.app.accounts.advisory_lock import serialize_per_email
from herhealth_backend.app.accounts.email_sender import EmailSender
from herhealth_backend.app.accounts.emails import normalize_email
from herhealth_backend.app.accounts.errors import (
    IncorrectVerificationCode,
    TooManyVerificationRequests,
    VerificationCodeExpired,
)
from herhealth_backend.app.accounts.models import EmailVerificationCode, User
from herhealth_backend.app.accounts.verification_code_policy import CODE_TTL, MAX_ATTEMPTS
from herhealth_backend.app.accounts.verification_codes import codes_match, generate_code, hash_code
from herhealth_backend.app.accounts.verification_send_throttle import (
    is_send_locked_out,
    record_send,
)

__all__ = ["send_verification_code", "request_verification_resend", "verify_email"]

_logger = logging.getLogger(__name__)

#: Namespaces this module's use of advisory_lock.serialize_per_email away
#: from other Accounts throttles (sign_in.py has its own).
_LOCK_NAMESPACE = "email-verification"


async def _issue_code(session: AsyncSession, secret: str, user: User) -> str:
    """Create or overwrite the one active code for ``user``. Returns the raw
    code — it is never persisted, only hashed. Caller commits.

    A single ``INSERT ... ON CONFLICT DO UPDATE``, not a read-then-branch:
    registration's own send and a resend request can land for the same user
    close enough together that a "does a row exist yet" SELECT followed by a
    separate INSERT would let both branches choose INSERT and collide on
    ``uq_email_verification_codes_user_id``. The database resolves the
    conflict atomically instead of either request needing to react to one.
    """
    code = generate_code()
    now = datetime.now(UTC)
    values = {
        "user_id": user.id,
        "code_hash": hash_code(secret, code),
        "created_at": now,
        "expires_at": now + CODE_TTL,
        "attempts": 0,
        "used_at": None,
    }
    stmt = pg_insert(EmailVerificationCode).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=[EmailVerificationCode.user_id],
        set_=values,
    )
    await session.execute(stmt)
    return code


async def _send(email_sender: EmailSender, *, to: str, code: str) -> None:
    try:
        await email_sender.send_verification_code(to=to, code=code)
    except Exception:
        # The code is already committed and valid regardless of whether this
        # delivery attempt succeeds — #10's own framing is that a delivery
        # failure must degrade the product, not strand her at a screen. She
        # can request another send if this one never arrives.
        _logger.exception("failed to send verification code to %s", to)


async def send_verification_code(
    session: AsyncSession, secret: str, email_sender: EmailSender, user: User
) -> None:
    """Send ``user`` a fresh code. Called right after registration.

    Takes the same per-email lock :func:`request_verification_resend` and
    :func:`verify_email` do — see this module's docstring — so a resend
    request racing registration's own first send cannot interleave with it.
    """
    await serialize_per_email(session, _LOCK_NAMESPACE, user.email)
    code = await _issue_code(session, secret, user)
    await record_send(session, user.email)
    await session.commit()
    await _send(email_sender, to=user.email, code=code)


async def request_verification_resend(
    session: AsyncSession, secret: str, email_sender: EmailSender, *, email: str
) -> None:
    """The "send me a new code" use case.

    Raises :class:`TooManyVerificationRequests` if this address has been sent
    too many codes recently (see ``verification_send_throttle.py``) —
    checked, and a throttle event recorded, before looking at whether the
    address is even registered, so the throttle itself cannot become a way
    to learn that. Silently does nothing beyond that (no error, no
    distinguishing response) for an address with no account, or one already
    verified — #10's own framing: this must not be usable to mail someone
    who never asked, nor to confirm whether an address is registered.
    """
    normalized_email = normalize_email(email)
    await serialize_per_email(session, _LOCK_NAMESPACE, normalized_email)
    if await is_send_locked_out(session, normalized_email):
        await session.commit()
        raise TooManyVerificationRequests()

    user = await session.scalar(select(User).where(User.email == normalized_email))
    code: str | None = None
    if user is not None and not user.email_verified:
        code = await _issue_code(session, secret, user)

    await record_send(session, normalized_email)
    await session.commit()

    if code is not None:
        assert user is not None
        await _send(email_sender, to=user.email, code=code)


async def verify_email(session: AsyncSession, secret: str, *, email: str, code: str) -> User:
    """Mark the address verified if ``code`` is the live code for it.

    Raises :class:`VerificationCodeExpired` if there is no code left that any
    digits could satisfy — none was ever requested, it passed CODE_TTL, it
    was already used, or MAX_ATTEMPTS wrong guesses used it up. Raises
    :class:`IncorrectVerificationCode` if a still-live code exists but
    ``code`` does not match it — and counts this as one of those attempts.

    Takes the same per-email lock the other two functions in this module do
    — the whole point is one mutex over every decision that reads or writes
    this address's verification state, not just this function's own
    attempts counter against itself. Without it, a resend racing a
    submission of the still-live code (its request already past the "is
    this address already verified" check but not yet committed) could
    silently overwrite the code the submission is about to accept, or reissue
    a code the resend's own check believed to be unnecessary.
    """
    normalized_email = normalize_email(email)
    await serialize_per_email(session, _LOCK_NAMESPACE, normalized_email)
    user = await session.scalar(select(User).where(User.email == normalized_email))

    row = None
    if user is not None:
        row = await session.scalar(
            select(EmailVerificationCode).where(EmailVerificationCode.user_id == user.id)
        )

    now = datetime.now(UTC)
    if (
        user is None
        or row is None
        or row.used_at is not None
        or row.attempts >= MAX_ATTEMPTS
        or row.expires_at <= now
    ):
        await session.commit()
        raise VerificationCodeExpired()

    if not codes_match(secret, code, row.code_hash):
        row.attempts += 1
        await session.commit()
        raise IncorrectVerificationCode()

    row.used_at = now
    user.email_verified = True
    await session.commit()
    return user
