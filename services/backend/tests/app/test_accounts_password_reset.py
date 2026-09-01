"""``password_reset`` use cases against a real (rolled-back) PostgreSQL transaction."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from conftest import StaticGoogleTokenVerifier
from herhealth_backend.app.accounts.email_verification import send_verification_code, verify_email
from herhealth_backend.app.accounts.errors import (
    IncorrectPasswordResetCode,
    InvalidSession,
    NoPasswordCredential,
    PasswordResetCodeExpired,
    TooManyPasswordResetRequests,
)
from herhealth_backend.app.accounts.google_identity import GoogleIdentity
from herhealth_backend.app.accounts.google_sign_in import sign_in_with_google
from herhealth_backend.app.accounts.models import Credential, PasswordResetCode, User
from herhealth_backend.app.accounts.password_policy import PasswordTooWeak
from herhealth_backend.app.accounts.password_reset import request_password_reset, reset_password
from herhealth_backend.app.accounts.password_reset_policy import MAX_ATTEMPTS
from herhealth_backend.app.accounts.password_reset_throttle import MAX_SENDS
from herhealth_backend.app.accounts.passwords import verify_password
from herhealth_backend.app.accounts.registration import register_user
from herhealth_backend.app.accounts.sessions import get_active_session, start_session

_SECRET = "unit-test-secret"


async def _a_verified_user(
    db_session: AsyncSession, email_sender, email: str = "woman@example.com"
) -> User:
    """A registered, verified user with a password credential — the
    starting state every "request a code" test in this suite needs.
    Reuses email_verification.py's own flow rather than flipping
    ``email_verified`` directly, so these tests exercise the same path #10
    already covers.
    """
    user = await register_user(db_session, email=email, password="correcthorse1")
    await send_verification_code(db_session, _SECRET, email_sender, user)
    code = email_sender.code_for(email)
    return await verify_email(db_session, _SECRET, email=email, code=code)


async def test_request_sends_a_code_for_a_verified_address_with_a_password(
    db_session: AsyncSession, email_sender
) -> None:
    await _a_verified_user(db_session, email_sender)

    await request_password_reset(db_session, _SECRET, email_sender, email="woman@example.com")

    code = email_sender.password_reset_code_for("woman@example.com")
    assert len(code) == 6 and code.isdigit()


async def test_request_stores_only_a_hash(db_session: AsyncSession, email_sender) -> None:
    user = await _a_verified_user(db_session, email_sender)

    await request_password_reset(db_session, _SECRET, email_sender, email="woman@example.com")

    row = await db_session.scalar(
        select(PasswordResetCode).where(PasswordResetCode.user_id == user.id)
    )
    assert row is not None
    code = email_sender.password_reset_code_for("woman@example.com")
    assert code not in row.code_hash


async def test_request_does_nothing_for_an_unknown_address(
    db_session: AsyncSession, email_sender
) -> None:
    await request_password_reset(db_session, _SECRET, email_sender, email="nobody@example.com")

    assert email_sender.password_reset_sent == []


async def test_request_does_nothing_for_an_unverified_address(
    db_session: AsyncSession, email_sender
) -> None:
    """Verification gates account recovery — an unverified address must read
    exactly like an unknown one, not like a real request."""
    await register_user(db_session, email="unverified@example.com", password="correcthorse1")

    await request_password_reset(db_session, _SECRET, email_sender, email="unverified@example.com")

    assert email_sender.password_reset_sent == []


async def test_request_raises_for_a_google_only_account(
    db_session: AsyncSession, google_verifier: StaticGoogleTokenVerifier, email_sender
) -> None:
    google_verifier.identity = GoogleIdentity(
        sub="google-sub-reset-1", email="google-only@example.com", email_verified=True
    )
    await sign_in_with_google(db_session, _SECRET, google_verifier, id_token="whatever")

    with pytest.raises(NoPasswordCredential):
        await request_password_reset(
            db_session, _SECRET, email_sender, email="google-only@example.com"
        )

    assert email_sender.password_reset_sent == []


async def test_request_does_nothing_for_an_unverified_google_only_account(
    db_session: AsyncSession, google_verifier: StaticGoogleTokenVerifier, email_sender
) -> None:
    """A Google-only account can still be unverified — Google's own token
    can carry ``email_verified: false`` (``google_identity.py``), and
    ``sign_in_with_google``'s new-user branch creates the row as-is. This
    must read exactly like an unknown address, not like the verified
    Google-only case above: raising ``NoPasswordCredential`` here would leak
    that the address is registered before she has ever proven she controls
    it.
    """
    google_verifier.identity = GoogleIdentity(
        sub="google-sub-reset-unverified",
        email="google-only-unverified@example.com",
        email_verified=False,
    )
    await sign_in_with_google(db_session, _SECRET, google_verifier, id_token="whatever")

    await request_password_reset(
        db_session, _SECRET, email_sender, email="google-only-unverified@example.com"
    )

    assert email_sender.password_reset_sent == []


async def test_repeated_requests_are_rate_limited(db_session: AsyncSession, email_sender) -> None:
    await _a_verified_user(db_session, email_sender)

    for _ in range(MAX_SENDS):
        await request_password_reset(db_session, _SECRET, email_sender, email="woman@example.com")

    with pytest.raises(TooManyPasswordResetRequests):
        await request_password_reset(db_session, _SECRET, email_sender, email="woman@example.com")


async def test_request_lockout_applies_even_to_an_unknown_address(
    db_session: AsyncSession, email_sender
) -> None:
    for _ in range(MAX_SENDS):
        await request_password_reset(db_session, _SECRET, email_sender, email="nobody@example.com")

    with pytest.raises(TooManyPasswordResetRequests):
        await request_password_reset(db_session, _SECRET, email_sender, email="nobody@example.com")


async def test_reset_with_the_correct_code_replaces_the_password(
    db_session: AsyncSession, email_sender
) -> None:
    user = await _a_verified_user(db_session, email_sender)
    await request_password_reset(db_session, _SECRET, email_sender, email="woman@example.com")
    code = email_sender.password_reset_code_for("woman@example.com")

    await reset_password(
        db_session, _SECRET, email="woman@example.com", code=code, new_password="newpassword1"
    )

    credential = await db_session.scalar(select(Credential).where(Credential.user_id == user.id))
    assert credential is not None
    assert verify_password(credential.password_hash, "newpassword1") is True
    assert verify_password(credential.password_hash, "correcthorse1") is False


async def test_reset_ends_every_existing_session(db_session: AsyncSession, email_sender) -> None:
    user = await _a_verified_user(db_session, email_sender)
    _, first_refresh_token = await start_session(db_session, _SECRET, user)
    _, second_refresh_token = await start_session(db_session, _SECRET, user)
    await db_session.commit()

    await request_password_reset(db_session, _SECRET, email_sender, email="woman@example.com")
    code = email_sender.password_reset_code_for("woman@example.com")
    await reset_password(
        db_session, _SECRET, email="woman@example.com", code=code, new_password="newpassword1"
    )

    with pytest.raises(InvalidSession):
        await get_active_session(db_session, first_refresh_token)
    with pytest.raises(InvalidSession):
        await get_active_session(db_session, second_refresh_token)


async def test_reset_with_no_code_ever_sent_is_expired(
    db_session: AsyncSession, email_sender
) -> None:
    await _a_verified_user(db_session, email_sender)

    with pytest.raises(PasswordResetCodeExpired):
        await reset_password(
            db_session,
            _SECRET,
            email="woman@example.com",
            code="000000",
            new_password="newpassword1",
        )


async def test_reset_with_an_unknown_address_is_expired(db_session: AsyncSession) -> None:
    with pytest.raises(PasswordResetCodeExpired):
        await reset_password(
            db_session,
            _SECRET,
            email="nobody@example.com",
            code="000000",
            new_password="newpassword1",
        )


async def test_reset_with_the_wrong_code_is_incorrect_not_expired(
    db_session: AsyncSession, email_sender
) -> None:
    await _a_verified_user(db_session, email_sender)
    await request_password_reset(db_session, _SECRET, email_sender, email="woman@example.com")
    code = email_sender.password_reset_code_for("woman@example.com")
    wrong_code = "0" * 6 if code != "0" * 6 else "1" * 6

    with pytest.raises(IncorrectPasswordResetCode):
        await reset_password(
            db_session,
            _SECRET,
            email="woman@example.com",
            code=wrong_code,
            new_password="newpassword1",
        )


async def test_reset_a_code_cannot_be_replayed(db_session: AsyncSession, email_sender) -> None:
    await _a_verified_user(db_session, email_sender)
    await request_password_reset(db_session, _SECRET, email_sender, email="woman@example.com")
    code = email_sender.password_reset_code_for("woman@example.com")
    await reset_password(
        db_session, _SECRET, email="woman@example.com", code=code, new_password="newpassword1"
    )

    with pytest.raises(PasswordResetCodeExpired):
        await reset_password(
            db_session,
            _SECRET,
            email="woman@example.com",
            code=code,
            new_password="anothernewpassword1",
        )


async def test_reset_rejects_an_expired_code(db_session: AsyncSession, email_sender) -> None:
    await _a_verified_user(db_session, email_sender)
    await request_password_reset(db_session, _SECRET, email_sender, email="woman@example.com")
    code = email_sender.password_reset_code_for("woman@example.com")
    row = await db_session.scalar(select(PasswordResetCode))
    assert row is not None
    row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await db_session.commit()

    with pytest.raises(PasswordResetCodeExpired):
        await reset_password(
            db_session, _SECRET, email="woman@example.com", code=code, new_password="newpassword1"
        )


async def test_reset_invalidates_the_code_after_max_attempts(
    db_session: AsyncSession, email_sender
) -> None:
    await _a_verified_user(db_session, email_sender)
    await request_password_reset(db_session, _SECRET, email_sender, email="woman@example.com")
    code = email_sender.password_reset_code_for("woman@example.com")
    wrong_code = "0" * 6 if code != "0" * 6 else "1" * 6

    for _ in range(MAX_ATTEMPTS):
        with pytest.raises(IncorrectPasswordResetCode):
            await reset_password(
                db_session,
                _SECRET,
                email="woman@example.com",
                code=wrong_code,
                new_password="newpassword1",
            )

    with pytest.raises(PasswordResetCodeExpired):
        await reset_password(
            db_session, _SECRET, email="woman@example.com", code=code, new_password="newpassword1"
        )


async def test_reset_rejects_a_weak_new_password_without_consuming_the_code(
    db_session: AsyncSession, email_sender
) -> None:
    await _a_verified_user(db_session, email_sender)
    await request_password_reset(db_session, _SECRET, email_sender, email="woman@example.com")
    code = email_sender.password_reset_code_for("woman@example.com")

    with pytest.raises(PasswordTooWeak):
        await reset_password(
            db_session, _SECRET, email="woman@example.com", code=code, new_password="short"
        )

    # The code is still live — a weak password does not use up the attempt.
    await reset_password(
        db_session, _SECRET, email="woman@example.com", code=code, new_password="newpassword1"
    )


async def test_a_fresh_request_supersedes_the_previous_code(
    db_session: AsyncSession, email_sender
) -> None:
    await _a_verified_user(db_session, email_sender)
    await request_password_reset(db_session, _SECRET, email_sender, email="woman@example.com")
    old_code = email_sender.password_reset_code_for("woman@example.com")

    await request_password_reset(db_session, _SECRET, email_sender, email="woman@example.com")
    new_code = email_sender.password_reset_code_for("woman@example.com")

    with pytest.raises(IncorrectPasswordResetCode):
        await reset_password(
            db_session,
            _SECRET,
            email="woman@example.com",
            code=old_code,
            new_password="newpassword1",
        )

    await reset_password(
        db_session, _SECRET, email="woman@example.com", code=new_code, new_password="newpassword1"
    )
