"""The password-reset use cases: requesting a code, completing the reset (#12).

Mirrors ``email_verification.py`` closely — a one-time code, HMAC-hashed,
overwritten on every fresh request, throttled per address — because #12's
"single-use link or code" resolves to exactly #10's pattern, and staying
consistent means one flow to review rather than two.

Two differences from email verification, both load-bearing:

- Only a *verified* address with a *password* credential is ever mailed a
  code. Verification gates account recovery (see ``services/backend/CONTEXT.md``'s
  own definition), so an unverified address is treated exactly like an
  unknown one — no code, no distinguishing response. An address with only a
  Google credential has nothing a password reset could touch, and #12 asks
  that she be told so plainly rather than mailed a code that cannot help —
  the one place this flow deliberately answers "does this account exist",
  because the alternative (silence) strands her looping between a reset
  screen and a sign-in screen that each point at the other.
- Completing a reset ends every session on the account (#12's fourth
  criterion) — a reset is exactly the scenario where someone else may hold
  her password, so leaving their session alive would defeat the point.

Takes the same per-email advisory lock ``email_verification.py`` does, under
its own namespace: one mutex over every decision that reads or writes a
given address's reset state, the same reasoning that module's own docstring
gives.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from anyio import to_thread
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from herhealth_backend.app.accounts.advisory_lock import serialize_per_email
from herhealth_backend.app.accounts.email_sender import EmailSender
from herhealth_backend.app.accounts.emails import normalize_email
from herhealth_backend.app.accounts.errors import (
    IncorrectPasswordResetCode,
    NoPasswordCredential,
    PasswordResetCodeExpired,
    TooManyPasswordResetRequests,
)
from herhealth_backend.app.accounts.models import (
    Credential,
    CredentialKind,
    PasswordResetCode,
    User,
)
from herhealth_backend.app.accounts.password_policy import check_password_strength
from herhealth_backend.app.accounts.password_reset_codes import (
    codes_match,
    generate_code,
    hash_code,
)
from herhealth_backend.app.accounts.password_reset_policy import CODE_TTL, MAX_ATTEMPTS
from herhealth_backend.app.accounts.password_reset_throttle import is_send_locked_out, record_send
from herhealth_backend.app.accounts.passwords import hash_password
from herhealth_backend.app.accounts.sessions import end_all_sessions

__all__ = ["request_password_reset", "reset_password"]

_logger = logging.getLogger(__name__)

#: Namespaces this module's use of advisory_lock.serialize_per_email away
#: from other Accounts throttles (email_verification.py has its own).
_LOCK_NAMESPACE = "password-reset"


async def _issue_code(session: AsyncSession, secret: str, user: User) -> str:
    """Create or overwrite the one active reset code for ``user``. Returns
    the raw code — it is never persisted, only hashed. Caller commits.

    Same ``INSERT ... ON CONFLICT DO UPDATE`` shape ``email_verification.py``'s
    ``_issue_code`` uses, and for the same reason: two requests for the same
    user close enough together must not collide on
    ``uq_password_reset_codes_user_id``.
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
    stmt = pg_insert(PasswordResetCode).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=[PasswordResetCode.user_id],
        set_=values,
    )
    await session.execute(stmt)
    return code


async def _send(email_sender: EmailSender, *, to: str, code: str) -> None:
    try:
        await email_sender.send_password_reset_code(to=to, code=code)
    except Exception:
        # The code is already committed and valid regardless of whether this
        # delivery attempt succeeds — the same reasoning email_verification.py's
        # own _send carries: a delivery failure must degrade the product, not
        # strand her at a screen. She can request another send if this one
        # never arrives.
        _logger.exception("failed to send password reset code to %s", to)


async def _password_credential(session: AsyncSession, user: User) -> Credential | None:
    return await session.scalar(
        select(Credential).where(
            Credential.user_id == user.id, Credential.kind == CredentialKind.PASSWORD
        )
    )


async def request_password_reset(
    session: AsyncSession, secret: str, email_sender: EmailSender, *, email: str
) -> None:
    """The "I forgot my password" use case.

    Raises :class:`TooManyPasswordResetRequests` if this address has been
    sent too many reset codes recently (see ``password_reset_throttle.py``)
    — checked, and a throttle event recorded, before looking at anything
    about the address, so the throttle itself cannot become a way to learn
    who is registered. Raises :class:`NoPasswordCredential` for a *verified*
    account with no password credential — see the module docstring for why
    this is the one deliberate exception to that rule. Gated on verification
    like everything else here: an unverified address must read exactly like
    an unknown one even when it happens to be Google-only, or the exception
    would leak that a real, still-unverified account sits behind it.
    Otherwise does nothing beyond recording the throttled attempt (no error,
    no distinguishing response) for an unknown address or an unverified one;
    sends a fresh code for a verified address with a password credential.
    """
    normalized_email = normalize_email(email)
    await serialize_per_email(session, _LOCK_NAMESPACE, normalized_email)
    if await is_send_locked_out(session, normalized_email):
        await session.commit()
        raise TooManyPasswordResetRequests()

    user = await session.scalar(select(User).where(User.email == normalized_email))

    no_password_credential = False
    code: str | None = None
    if user is not None and user.email_verified:
        if await _password_credential(session, user) is None:
            no_password_credential = True
        else:
            code = await _issue_code(session, secret, user)

    await record_send(session, normalized_email)
    await session.commit()

    if no_password_credential:
        raise NoPasswordCredential()

    if code is not None:
        assert user is not None
        await _send(email_sender, to=user.email, code=code)


async def reset_password(
    session: AsyncSession, secret: str, *, email: str, code: str, new_password: str
) -> User:
    """Replace the password credential if ``code`` is the live reset code for it.

    Raises :class:`PasswordResetCodeExpired` if there is no code left that
    any digits could satisfy — none was ever requested, it passed CODE_TTL,
    it was already used, or MAX_ATTEMPTS wrong guesses used it up. Raises
    :class:`IncorrectPasswordResetCode` if a still-live code exists but
    ``code`` does not match it — and counts this as one of those attempts.
    Raises :class:`NoPasswordCredential` in the defensive case where the
    account has no password credential left to replace by the time a live
    code is redeemed — not currently reachable (a code is only ever issued
    to a verified account, and ``google_sign_in.py``'s takeover branch,
    which is the only place a password credential is removed, applies only
    to *unverified* accounts), kept as a guard rather than an assertion so a
    future change to either invariant fails safely instead of silently.
    Raises
    :class:`~herhealth_backend.app.accounts.password_policy.PasswordTooWeak`
    if ``new_password`` does not clear the strength floor — checked only
    after the code itself is confirmed live and correct, so a wrong or
    expired code never reveals anything about the new password's validity,
    and the code is not consumed by a rejected password: she can retry the
    same code with a stronger one.

    Ends every session on the account on success (#12's fourth criterion).
    Takes the same per-email lock :func:`request_password_reset` does — see
    the module docstring.
    """
    normalized_email = normalize_email(email)
    await serialize_per_email(session, _LOCK_NAMESPACE, normalized_email)
    user = await session.scalar(select(User).where(User.email == normalized_email))

    row = None
    if user is not None:
        row = await session.scalar(
            select(PasswordResetCode).where(PasswordResetCode.user_id == user.id)
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
        raise PasswordResetCodeExpired()

    if not codes_match(secret, code, row.code_hash):
        row.attempts += 1
        await session.commit()
        raise IncorrectPasswordResetCode()

    credential = await _password_credential(session, user)
    if credential is None:
        await session.commit()
        raise NoPasswordCredential()

    check_password_strength(new_password)
    # argon2id is deliberately slow; run it off the event loop, as
    # registration.py and sign_in.py do.
    password_hash = await to_thread.run_sync(hash_password, new_password)

    credential.password_hash = password_hash
    row.used_at = now
    await end_all_sessions(session, user.id)
    await session.commit()
    return user
