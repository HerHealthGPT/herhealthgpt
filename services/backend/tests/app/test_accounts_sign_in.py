"""``sign_in`` against a real (rolled-back) PostgreSQL transaction."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from herhealth_backend.app.accounts.errors import InvalidCredentials, TooManySignInAttempts
from herhealth_backend.app.accounts.registration import register_user
from herhealth_backend.app.accounts.sign_in import sign_in
from herhealth_backend.app.accounts.sign_in_throttle import MAX_FAILURES
from herhealth_backend.app.accounts.tokens import read_access_token

_SECRET = "unit-test-secret"


async def _a_registered_user(db_session: AsyncSession) -> None:
    await register_user(db_session, email="woman@example.com", password="correcthorse1")


async def test_sign_in_with_correct_credentials_returns_a_session(
    db_session: AsyncSession,
) -> None:
    await _a_registered_user(db_session)

    user, access_token, refresh_token = await sign_in(
        db_session, _SECRET, email="Woman@Example.com", password="correcthorse1"
    )

    assert user.email == "woman@example.com"
    assert read_access_token(_SECRET, access_token) == str(user.id)
    assert refresh_token


async def test_sign_in_with_an_unknown_address_raises_invalid_credentials(
    db_session: AsyncSession,
) -> None:
    with pytest.raises(InvalidCredentials):
        await sign_in(db_session, _SECRET, email="nobody@example.com", password="whatever123")


async def test_sign_in_with_the_wrong_password_raises_invalid_credentials(
    db_session: AsyncSession,
) -> None:
    await _a_registered_user(db_session)

    with pytest.raises(InvalidCredentials):
        await sign_in(db_session, _SECRET, email="woman@example.com", password="wrongpassword1")


async def test_sign_in_is_blocked_after_too_many_failures(db_session: AsyncSession) -> None:
    await _a_registered_user(db_session)

    for _ in range(MAX_FAILURES):
        with pytest.raises(InvalidCredentials):
            await sign_in(db_session, _SECRET, email="woman@example.com", password="wrong")

    with pytest.raises(TooManySignInAttempts):
        await sign_in(db_session, _SECRET, email="woman@example.com", password="correcthorse1")


async def test_a_successful_sign_in_clears_earlier_failures(db_session: AsyncSession) -> None:
    await _a_registered_user(db_session)

    for _ in range(MAX_FAILURES - 1):
        with pytest.raises(InvalidCredentials):
            await sign_in(db_session, _SECRET, email="woman@example.com", password="wrong")

    await sign_in(db_session, _SECRET, email="woman@example.com", password="correcthorse1")

    # The earlier near-lockout failures were cleared by the success above, so
    # this single fresh failure must not trip the lockout on its own.
    with pytest.raises(InvalidCredentials):
        await sign_in(db_session, _SECRET, email="woman@example.com", password="wrong")
