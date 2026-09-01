"""``sign_in_with_google`` against a real (rolled-back) PostgreSQL transaction."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from conftest import StaticGoogleTokenVerifier
from herhealth_backend.app.accounts.errors import GoogleEmailNotVerified, InvalidSession
from herhealth_backend.app.accounts.google_identity import GoogleIdentity
from herhealth_backend.app.accounts.google_sign_in import sign_in_with_google
from herhealth_backend.app.accounts.models import Credential, CredentialKind, User
from herhealth_backend.app.accounts.registration import register_user
from herhealth_backend.app.accounts.sessions import get_active_session, start_session
from herhealth_backend.app.accounts.tokens import read_access_token

_SECRET = "unit-test-secret"


async def test_google_sign_in_on_an_unknown_address_creates_a_user_with_no_password(
    db_session: AsyncSession, google_verifier: StaticGoogleTokenVerifier
) -> None:
    google_verifier.identity = GoogleIdentity(
        sub="google-sub-1", email="new-woman@example.com", email_verified=True
    )

    user, access_token, _ = await sign_in_with_google(
        db_session, _SECRET, google_verifier, id_token="whatever"
    )

    assert user.email == "new-woman@example.com"
    assert read_access_token(_SECRET, access_token) == str(user.id)

    credentials = (
        await db_session.scalars(select(Credential).where(Credential.user_id == user.id))
    ).all()
    assert len(credentials) == 1
    assert credentials[0].kind == CredentialKind.GOOGLE
    assert credentials[0].google_subject == "google-sub-1"
    assert credentials[0].password_hash is None


async def test_google_sign_in_a_second_time_signs_into_the_same_user(
    db_session: AsyncSession, google_verifier: StaticGoogleTokenVerifier
) -> None:
    google_verifier.identity = GoogleIdentity(
        sub="google-sub-2", email="repeat-woman@example.com", email_verified=True
    )

    first_user, _, _ = await sign_in_with_google(
        db_session, _SECRET, google_verifier, id_token="t1"
    )
    second_user, _, _ = await sign_in_with_google(
        db_session, _SECRET, google_verifier, id_token="t2"
    )

    assert second_user.id == first_user.id
    credentials = (
        await db_session.scalars(select(Credential).where(Credential.user_id == first_user.id))
    ).all()
    assert len(credentials) == 1


async def test_google_sign_in_links_to_a_verified_existing_user(
    db_session: AsyncSession, google_verifier: StaticGoogleTokenVerifier
) -> None:
    user = await register_user(db_session, email="verified@example.com", password="correcthorse1")
    user.email_verified = True
    await db_session.commit()

    google_verifier.identity = GoogleIdentity(
        sub="google-sub-3", email="Verified@Example.com", email_verified=True
    )
    linked_user, _, _ = await sign_in_with_google(
        db_session, _SECRET, google_verifier, id_token="whatever"
    )

    assert linked_user.id == user.id
    credentials = (
        await db_session.scalars(select(Credential).where(Credential.user_id == user.id))
    ).all()
    kinds = {c.kind for c in credentials}
    assert kinds == {CredentialKind.PASSWORD, CredentialKind.GOOGLE}


async def test_google_sign_in_takes_over_an_unverified_existing_user(
    db_session: AsyncSession, google_verifier: StaticGoogleTokenVerifier
) -> None:
    """The explicit takeover case #11's acceptance criteria calls out: an
    unverified registration must not keep its access once the real owner's
    Google identity claims the account.
    """
    user = await register_user(db_session, email="squatted@example.com", password="correcthorse1")
    assert user.email_verified is False
    _, squatter_refresh_token = await start_session(db_session, _SECRET, user)
    await db_session.commit()

    google_verifier.identity = GoogleIdentity(
        sub="google-sub-4", email="squatted@example.com", email_verified=True
    )
    taken_over_user, _, _ = await sign_in_with_google(
        db_session, _SECRET, google_verifier, id_token="whatever"
    )

    assert taken_over_user.id == user.id
    assert taken_over_user.email_verified is True

    credentials = (
        await db_session.scalars(select(Credential).where(Credential.user_id == user.id))
    ).all()
    assert len(credentials) == 1
    assert credentials[0].kind == CredentialKind.GOOGLE

    # The squatter's session from before the takeover no longer works.
    with pytest.raises(InvalidSession):
        await get_active_session(db_session, squatter_refresh_token)


async def test_google_sign_in_refuses_to_link_when_google_does_not_assert_verification(
    db_session: AsyncSession, google_verifier: StaticGoogleTokenVerifier
) -> None:
    user = await register_user(
        db_session, email="careful-woman@example.com", password="correcthorse1"
    )
    user.email_verified = True
    await db_session.commit()

    google_verifier.identity = GoogleIdentity(
        sub="google-sub-5", email="careful-woman@example.com", email_verified=False
    )

    with pytest.raises(GoogleEmailNotVerified):
        await sign_in_with_google(db_session, _SECRET, google_verifier, id_token="whatever")

    credentials = (
        await db_session.scalars(select(Credential).where(Credential.user_id == user.id))
    ).all()
    assert len(credentials) == 1
    assert credentials[0].kind == CredentialKind.PASSWORD


async def test_google_sign_in_refuses_takeover_when_google_does_not_assert_verification(
    db_session: AsyncSession, google_verifier: StaticGoogleTokenVerifier
) -> None:
    user = await register_user(
        db_session, email="unverified-target@example.com", password="correcthorse1"
    )
    assert user.email_verified is False

    google_verifier.identity = GoogleIdentity(
        sub="google-sub-6", email="unverified-target@example.com", email_verified=False
    )

    with pytest.raises(GoogleEmailNotVerified):
        await sign_in_with_google(db_session, _SECRET, google_verifier, id_token="whatever")

    fresh = await db_session.scalar(select(User).where(User.id == user.id))
    assert fresh is not None
    assert fresh.email_verified is False


async def test_google_subject_is_the_join_key_not_the_email(
    db_session: AsyncSession, google_verifier: StaticGoogleTokenVerifier
) -> None:
    """#11's fifth acceptance criterion: changing the address on the Google
    side does not orphan the account — a later sign-in with the same
    subject but a different email still reaches the same user.
    """
    google_verifier.identity = GoogleIdentity(
        sub="google-sub-7", email="old-address@example.com", email_verified=True
    )
    first_user, _, _ = await sign_in_with_google(
        db_session, _SECRET, google_verifier, id_token="t1"
    )

    google_verifier.identity = GoogleIdentity(
        sub="google-sub-7", email="new-address@example.com", email_verified=True
    )
    second_user, _, _ = await sign_in_with_google(
        db_session, _SECRET, google_verifier, id_token="t2"
    )

    assert second_user.id == first_user.id
