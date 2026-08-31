"""The registration use case: an address and a password become a user.

Deliberately does not sign her in and does not send a verification code — #9
and #10 own those. This function's whole job is "a user exists, unverified,
with one password credential," and nothing more.
"""

from __future__ import annotations

from anyio import to_thread
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from herhealth_backend.app.accounts.emails import normalize_email
from herhealth_backend.app.accounts.errors import EmailAlreadyRegistered
from herhealth_backend.app.accounts.models import Credential, CredentialKind, User
from herhealth_backend.app.accounts.password_policy import check_password_strength
from herhealth_backend.app.accounts.passwords import hash_password

#: The unique constraint (see the accounts migration) that a commit-time
#: IntegrityError must name for it to mean "this address is already
#: registered" — anything else is a real defect and must not be swallowed.
_EMAIL_UNIQUE_CONSTRAINT = "uq_users_email"

__all__ = ["register_user"]


async def register_user(session: AsyncSession, *, email: str, password: str) -> User:
    """Create an unverified user with one password credential.

    Raises :class:`~herhealth_backend.app.accounts.password_policy.PasswordTooWeak`
    if ``password`` does not clear the strength floor, and
    :class:`~herhealth_backend.app.accounts.errors.EmailAlreadyRegistered` if a
    user already holds the normalised address. The strength check runs before
    any query, so a weak password never touches the database.
    """
    check_password_strength(password)

    normalized_email = normalize_email(email)
    existing = await session.scalar(select(User).where(User.email == normalized_email))
    if existing is not None:
        raise EmailAlreadyRegistered()

    # argon2id is deliberately slow and memory-hard; run it off the event loop
    # so one registration cannot stall every other coroutine in the process,
    # including the health check.
    password_hash = await to_thread.run_sync(hash_password, password)

    user = User(email=normalized_email, email_verified=False)
    user.credentials.append(Credential(kind=CredentialKind.PASSWORD, password_hash=password_hash))
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as exc:
        # Two concurrent registrations for the same address both pass the
        # SELECT above; the unique constraint on users.email is what actually
        # decides it. Anything else (a check constraint tripped by a bug, for
        # instance) is a real defect and must surface as one, not get
        # relabelled as a duplicate address.
        await session.rollback()
        constraint_name = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
        if constraint_name != _EMAIL_UNIQUE_CONSTRAINT:
            raise
        raise EmailAlreadyRegistered() from exc

    await session.refresh(user)
    return user
