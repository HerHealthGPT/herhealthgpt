"""``email_verification`` use cases against a real (rolled-back) PostgreSQL transaction."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from herhealth_backend.app.accounts.email_verification import (
    request_verification_resend,
    send_verification_code,
    verify_email,
)
from herhealth_backend.app.accounts.errors import (
    IncorrectVerificationCode,
    TooManyVerificationRequests,
    VerificationCodeExpired,
)
from herhealth_backend.app.accounts.models import EmailVerificationCode, User
from herhealth_backend.app.accounts.registration import register_user
from herhealth_backend.app.accounts.verification_code_policy import MAX_ATTEMPTS
from herhealth_backend.app.accounts.verification_send_throttle import MAX_SENDS

_SECRET = "unit-test-secret"


async def _a_user(db_session: AsyncSession, email: str = "woman@example.com") -> User:
    return await register_user(db_session, email=email, password="correcthorse1")


async def test_send_verification_code_emails_the_user(
    db_session: AsyncSession, email_sender
) -> None:
    user = await _a_user(db_session)

    await send_verification_code(db_session, _SECRET, email_sender, user)

    code = email_sender.code_for("woman@example.com")
    assert len(code) == 6 and code.isdigit()


async def test_send_verification_code_stores_only_a_hash(
    db_session: AsyncSession, email_sender
) -> None:
    user = await _a_user(db_session)

    await send_verification_code(db_session, _SECRET, email_sender, user)

    row = await db_session.scalar(
        select(EmailVerificationCode).where(EmailVerificationCode.user_id == user.id)
    )
    assert row is not None
    code = email_sender.code_for("woman@example.com")
    assert code not in row.code_hash


async def test_verify_email_with_the_correct_code_marks_the_address_verified(
    db_session: AsyncSession, email_sender
) -> None:
    user = await _a_user(db_session)
    await send_verification_code(db_session, _SECRET, email_sender, user)
    code = email_sender.code_for("woman@example.com")

    verified_user = await verify_email(db_session, _SECRET, email="woman@example.com", code=code)

    assert verified_user.email_verified is True


async def test_verify_email_with_no_code_ever_sent_is_expired(db_session: AsyncSession) -> None:
    await _a_user(db_session)

    with pytest.raises(VerificationCodeExpired):
        await verify_email(db_session, _SECRET, email="woman@example.com", code="000000")


async def test_verify_email_with_an_unknown_address_is_expired(db_session: AsyncSession) -> None:
    with pytest.raises(VerificationCodeExpired):
        await verify_email(db_session, _SECRET, email="nobody@example.com", code="000000")


async def test_verify_email_with_the_wrong_code_is_incorrect_not_expired(
    db_session: AsyncSession, email_sender
) -> None:
    user = await _a_user(db_session)
    await send_verification_code(db_session, _SECRET, email_sender, user)
    code = email_sender.code_for("woman@example.com")
    wrong_code = "0" * 6 if code != "0" * 6 else "1" * 6

    with pytest.raises(IncorrectVerificationCode):
        await verify_email(db_session, _SECRET, email="woman@example.com", code=wrong_code)


async def test_verify_email_a_code_cannot_be_replayed(
    db_session: AsyncSession, email_sender
) -> None:
    user = await _a_user(db_session)
    await send_verification_code(db_session, _SECRET, email_sender, user)
    code = email_sender.code_for("woman@example.com")
    await verify_email(db_session, _SECRET, email="woman@example.com", code=code)

    with pytest.raises(VerificationCodeExpired):
        await verify_email(db_session, _SECRET, email="woman@example.com", code=code)


async def test_verify_email_rejects_an_expired_code(
    db_session: AsyncSession, email_sender
) -> None:
    user = await _a_user(db_session)
    await send_verification_code(db_session, _SECRET, email_sender, user)
    code = email_sender.code_for("woman@example.com")
    row = await db_session.scalar(
        select(EmailVerificationCode).where(EmailVerificationCode.user_id == user.id)
    )
    assert row is not None
    row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await db_session.commit()

    with pytest.raises(VerificationCodeExpired):
        await verify_email(db_session, _SECRET, email="woman@example.com", code=code)


async def test_verify_email_invalidates_the_code_after_max_attempts(
    db_session: AsyncSession, email_sender
) -> None:
    user = await _a_user(db_session)
    await send_verification_code(db_session, _SECRET, email_sender, user)
    code = email_sender.code_for("woman@example.com")
    wrong_code = "0" * 6 if code != "0" * 6 else "1" * 6

    for _ in range(MAX_ATTEMPTS):
        with pytest.raises(IncorrectVerificationCode):
            await verify_email(db_session, _SECRET, email="woman@example.com", code=wrong_code)

    # Even the correct code no longer works — too many wrong guesses used it up.
    with pytest.raises(VerificationCodeExpired):
        await verify_email(db_session, _SECRET, email="woman@example.com", code=code)


async def test_a_resend_supersedes_the_previous_code(
    db_session: AsyncSession, email_sender
) -> None:
    user = await _a_user(db_session)
    await send_verification_code(db_session, _SECRET, email_sender, user)
    old_code = email_sender.code_for("woman@example.com")

    await request_verification_resend(
        db_session, _SECRET, email_sender, email="woman@example.com"
    )
    new_code = email_sender.code_for("woman@example.com")

    # A 1-in-a-million coincidence (old_code == new_code) would make this a
    # false failure rather than a false pass, and is not worth guarding against.
    with pytest.raises(IncorrectVerificationCode):
        await verify_email(db_session, _SECRET, email="woman@example.com", code=old_code)

    await verify_email(db_session, _SECRET, email="woman@example.com", code=new_code)


async def test_resend_does_nothing_for_an_unknown_address(
    db_session: AsyncSession, email_sender
) -> None:
    await request_verification_resend(
        db_session, _SECRET, email_sender, email="nobody@example.com"
    )

    assert email_sender.sent == []


async def test_resend_does_nothing_for_an_already_verified_address(
    db_session: AsyncSession, email_sender
) -> None:
    user = await _a_user(db_session)
    await send_verification_code(db_session, _SECRET, email_sender, user)
    code = email_sender.code_for("woman@example.com")
    await verify_email(db_session, _SECRET, email="woman@example.com", code=code)
    email_sender.sent.clear()

    await request_verification_resend(
        db_session, _SECRET, email_sender, email="woman@example.com"
    )

    assert email_sender.sent == []


async def test_repeated_resend_requests_are_blocked(
    db_session: AsyncSession, email_sender
) -> None:
    await _a_user(db_session)

    for _ in range(MAX_SENDS):
        await request_verification_resend(
            db_session, _SECRET, email_sender, email="woman@example.com"
        )

    with pytest.raises(TooManyVerificationRequests):
        await request_verification_resend(
            db_session, _SECRET, email_sender, email="woman@example.com"
        )


async def test_resend_lockout_applies_even_to_an_unknown_address(
    db_session: AsyncSession, email_sender
) -> None:
    """The throttle must count a request against an unregistered address the
    same as a registered one, or its absence would itself reveal that the
    address does not exist.
    """
    for _ in range(MAX_SENDS):
        await request_verification_resend(
            db_session, _SECRET, email_sender, email="nobody@example.com"
        )

    with pytest.raises(TooManyVerificationRequests):
        await request_verification_resend(
            db_session, _SECRET, email_sender, email="nobody@example.com"
        )
