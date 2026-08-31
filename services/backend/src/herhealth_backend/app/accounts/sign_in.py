"""The sign-in use case: credentials in, a session out.

Deliberately raises the same :class:`~herhealth_backend.app.accounts.errors.InvalidCredentials`
for an unknown address and for a wrong password on a real one (#9's second
acceptance criterion), and does the same amount of work either way — a fixed
dummy hash stands in for a missing credential so a timing difference cannot
do what the shared exception is built not to.
"""

from __future__ import annotations

from anyio import to_thread
from sqlalchemy import and_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from herhealth_backend.app.accounts.emails import normalize_email
from herhealth_backend.app.accounts.errors import InvalidCredentials, TooManySignInAttempts
from herhealth_backend.app.accounts.models import Credential, CredentialKind, User
from herhealth_backend.app.accounts.passwords import verify_password
from herhealth_backend.app.accounts.sessions import start_session
from herhealth_backend.app.accounts.sign_in_throttle import (
    clear_failures,
    is_locked_out,
    record_failure,
)

__all__ = ["sign_in"]

#: A real argon2id hash of a fixed string that is not, and must never become,
#: an actual credential. Verifying against it costs the same as verifying
#: against a real password hash, so an unknown address takes as long to
#: reject as a wrong password on a known one.
_DUMMY_PASSWORD_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4$c+SRggg5Nh2qO2mryS2hIA$"
    "AM01hu2OP7XAxZgUtFqLMwgQGKOSeupQVfowdVj/grI"
)


async def _serialize_per_email(session: AsyncSession, email: str) -> None:
    """Block until no other in-flight decision for ``email`` holds this lock.

    ``is_locked_out`` (a SELECT) and ``record_failure`` (an INSERT) are not
    atomic on their own: under READ COMMITTED, concurrent requests for the
    same address can each read the failure count before any of the others'
    inserts commit, letting all of them through at once regardless of
    MAX_FAILURES. A transaction-scoped advisory lock, keyed by the address,
    serializes the *decision* (check-then-write) so each request sees the
    others' committed failures first.

    Deliberately acquired only around that decision in :func:`sign_in`, never
    around the argon2id verify — holding it there too would serialize even
    unrelated, legitimate concurrent sign-ins for one address behind whatever
    hashing cost the first happened to take, turning a fix for a counting
    race into a latency lever anyone could pull against a chosen address.
    Committing (or rolling back) releases the lock; nothing to clean up.
    """
    await session.execute(text("SELECT pg_advisory_xact_lock(hashtext(:email))"), {"email": email})


async def _authenticate(
    session: AsyncSession, normalized_email: str, password: str
) -> User | None:
    # One query, not a SELECT plus a separate selectinload round trip: an
    # outer join to the (at most one) password credential, filtered by kind
    # in the join condition rather than in Python.
    result = await session.execute(
        select(User, Credential)
        .outerjoin(
            Credential,
            and_(Credential.user_id == User.id, Credential.kind == CredentialKind.PASSWORD),
        )
        .where(User.email == normalized_email)
    )
    row = result.first()
    user, credential = row if row is not None else (None, None)
    password_hash = credential.password_hash if credential is not None else _DUMMY_PASSWORD_HASH
    # argon2id is deliberately slow; run it off the event loop, as registration does.
    valid = await to_thread.run_sync(verify_password, password_hash, password)
    if user is None or credential is None or not valid:
        return None
    return user


async def sign_in(
    session: AsyncSession, secret: str, *, email: str, password: str
) -> tuple[User, str, str]:
    """Return ``(user, access_token, refresh_token)`` for correct credentials.

    Raises :class:`TooManySignInAttempts` if this address has failed too many
    times recently (see ``sign_in_throttle.py``), or
    :class:`InvalidCredentials` for an unknown address or a wrong password —
    the same exception either way. Commits on every path that changes state.
    """
    normalized_email = normalize_email(email)

    # The slow part — argon2id — runs unlocked. What must be atomic across
    # concurrent sign-ins for one address is only the decision right after
    # it: check the failure count, then write this attempt's outcome, as one
    # unit. See _serialize_per_email's docstring for why the lock stops here.
    user = await _authenticate(session, normalized_email, password)

    await _serialize_per_email(session, normalized_email)
    if await is_locked_out(session, normalized_email):
        await session.commit()
        raise TooManySignInAttempts()

    if user is None:
        await record_failure(session, normalized_email)
        await session.commit()
        raise InvalidCredentials()

    await clear_failures(session, normalized_email)
    access_token, refresh_token = await start_session(session, secret, user)
    await session.commit()
    return user, access_token, refresh_token
