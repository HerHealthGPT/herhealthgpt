"""The Google sign-in use case (#11): create, link, or take over an account.

This is where the vulnerability #11 exists to close or build in: if an
attacker registers a woman's address with a password and never verifies it,
and the service later links her real Google identity to that account on a
matching email string, he keeps whatever access his password credential
still gives him. The rule this module enforces:

- A Google identity already linked to a user signs into that user directly.
- Otherwise, an existing user at the identity's address is only *linked to*
  if she is verified **and** Google asserts the address is verified too —
  never on either alone.
- An existing but *unverified* user at that address is **taken over**, not
  linked to: her unverified registration proved nothing, Google proved
  inbox control. The old (unverified) credential is removed and every
  session on the account is ended — a squatter's sign-in, if she ever
  managed to sign in past a still-unverified account, does not survive
  someone else's Google identity taking the account back.
- No existing user at that address, with Google's claim either way, means a
  fresh account: nothing to take over or link to yet.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from herhealth_backend.app.accounts.advisory_lock import serialize_per_email
from herhealth_backend.app.accounts.emails import normalize_email
from herhealth_backend.app.accounts.errors import EmailAlreadyRegistered, GoogleEmailNotVerified
from herhealth_backend.app.accounts.google_identity import GoogleTokenVerifier
from herhealth_backend.app.accounts.models import Credential, CredentialKind, User
from herhealth_backend.app.accounts.sessions import end_all_sessions, start_session

__all__ = ["sign_in_with_google"]

_LOCK_NAMESPACE = "google-sign-in"

#: Constraints a commit-time IntegrityError in the new-user branch may
#: legitimately name — see sign_in_with_google's docstring on the race this
#: guards. Anything else is a real defect and must not be swallowed, the
#: same reasoning registration.py's own narrow catch is held to.
_EXPECTED_CONFLICT_CONSTRAINTS = frozenset({"uq_users_email", "uq_credentials_google_subject"})


async def _credential_for_subject(session: AsyncSession, sub: str) -> Credential | None:
    return await session.scalar(
        select(Credential).where(
            Credential.kind == CredentialKind.GOOGLE, Credential.google_subject == sub
        )
    )


async def _sign_in_as(
    session: AsyncSession, secret: str, user_id: uuid.UUID
) -> tuple[User, str, str]:
    user = await session.get(User, user_id)
    assert user is not None
    access_token, refresh_token = await start_session(session, secret, user)
    await session.commit()
    return user, access_token, refresh_token


async def sign_in_with_google(
    session: AsyncSession, secret: str, google_verifier: GoogleTokenVerifier, *, id_token: str
) -> tuple[User, str, str]:
    """Return ``(user, access_token, refresh_token)`` for a valid Google ID token.

    Raises :class:`~herhealth_backend.app.accounts.errors.GoogleTokenInvalid`
    if the token itself does not check out,
    :class:`~herhealth_backend.app.accounts.errors.GoogleEmailNotVerified`
    if it would otherwise need to link to or take over an existing user but
    Google does not assert the address is verified, or
    :class:`~herhealth_backend.app.accounts.errors.EmailAlreadyRegistered`
    in the narrow race where a concurrent registration or Google sign-in
    claims this address between this call's checks and its own commit —
    the same "someone else got there first" a retry of the request resolves
    cleanly, the row now existing to link to or take over instead.
    """
    # Verification first, unlocked: it may be a real network call (see
    # google_identity.py), and nothing here should hold a lock across that
    # the way #9 learned not to hold one across argon2id.
    identity = await google_verifier.verify(id_token)

    existing_credential = await _credential_for_subject(session, identity.sub)
    if existing_credential is not None:
        return await _sign_in_as(session, secret, existing_credential.user_id)

    normalized_email = normalize_email(identity.email)
    await serialize_per_email(session, _LOCK_NAMESPACE, normalized_email)

    # Re-checked under the lock: a concurrent sign-in with the same token
    # (a double-click, a retry) could have created this credential between
    # the unlocked check above and acquiring the lock.
    existing_credential = await _credential_for_subject(session, identity.sub)
    if existing_credential is not None:
        return await _sign_in_as(session, secret, existing_credential.user_id)

    # Linking and takeover both read and mutate existing_user.credentials —
    # eager-loaded so that stays a plain attribute access, not an async lazy
    # load MissingGreenlet would refuse outside the greenlet that fetched it.
    existing_user = await session.scalar(
        select(User).options(selectinload(User.credentials)).where(User.email == normalized_email)
    )

    if existing_user is None:
        user = User(email=normalized_email, email_verified=identity.email_verified)
        user.credentials.append(Credential(kind=CredentialKind.GOOGLE, google_subject=identity.sub))
        session.add(user)
        try:
            # start_session below needs user.id — a server-generated default
            # (gen_random_uuid()) that stays None on the Python side until
            # the INSERT actually runs, unlike existing_user in the other
            # branches.
            await session.flush()
        except IntegrityError as exc:
            # register_user() (#8) takes no lock of its own, so a password
            # registration for this exact address can still commit in the
            # gap between the SELECT above and this flush; a concurrent
            # Google sign-in whose token names the same sub is the same
            # shape of race on uq_credentials_google_subject instead.
            await session.rollback()
            constraint_name = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
            if constraint_name not in _EXPECTED_CONFLICT_CONSTRAINTS:
                raise
            raise EmailAlreadyRegistered() from exc
    elif not identity.email_verified:
        raise GoogleEmailNotVerified()
    elif existing_user.email_verified:
        # Linking: she already proved this address once; Google proves it again.
        existing_user.credentials.append(
            Credential(kind=CredentialKind.GOOGLE, google_subject=identity.sub)
        )
        user = existing_user
    else:
        # Takeover: her existing registration proved nothing; Google just did.
        for credential in list(existing_user.credentials):
            await session.delete(credential)
        existing_user.credentials.append(
            Credential(kind=CredentialKind.GOOGLE, google_subject=identity.sub)
        )
        existing_user.email_verified = True
        await end_all_sessions(session, existing_user.id)
        user = existing_user

    access_token, refresh_token = await start_session(session, secret, user)
    await session.commit()
    return user, access_token, refresh_token
