"""``register_user`` against a real (rolled-back) PostgreSQL transaction."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from herhealth_backend.app.accounts.errors import EmailAlreadyRegistered
from herhealth_backend.app.accounts.models import Credential, CredentialKind, User
from herhealth_backend.app.accounts.password_policy import PasswordTooWeak
from herhealth_backend.app.accounts.passwords import verify_password
from herhealth_backend.app.accounts.registration import register_user


def _integrity_error(constraint_name: str) -> IntegrityError:
    """A stand-in for the driver error register_user inspects, without a real race.

    ``exc.orig`` only needs to look enough like a psycopg error for
    ``getattr(exc.orig, "diag", None).constraint_name`` to resolve — the real
    ``psycopg.errors.UniqueViolation.diag`` is populated from a live server
    result and cannot be constructed by hand outside one.
    """
    orig = SimpleNamespace(diag=SimpleNamespace(constraint_name=constraint_name))
    return IntegrityError("INSERT", {}, orig)


async def test_register_user_creates_an_unverified_user(db_session: AsyncSession) -> None:
    user = await register_user(db_session, email="Woman@Example.com", password="correcthorse1")

    assert user.email == "woman@example.com"
    assert user.email_verified is False


async def test_register_user_stores_an_argon2id_password_credential(
    db_session: AsyncSession,
) -> None:
    user = await register_user(db_session, email="woman@example.com", password="correcthorse1")

    credential = await db_session.scalar(
        select(Credential).where(Credential.user_id == user.id)
    )
    assert credential is not None
    assert credential.kind == CredentialKind.PASSWORD
    assert credential.password_hash is not None
    assert credential.password_hash.startswith("$argon2id$")
    assert verify_password(credential.password_hash, "correcthorse1") is True


async def test_register_user_refuses_an_address_already_registered(
    db_session: AsyncSession,
) -> None:
    await register_user(db_session, email="woman@example.com", password="correcthorse1")

    with pytest.raises(EmailAlreadyRegistered):
        await register_user(db_session, email="WOMAN@EXAMPLE.COM", password="anotherpass1")

    users = (await db_session.scalars(select(User))).all()
    assert len(users) == 1


async def test_register_user_refuses_a_weak_password_without_creating_a_user(
    db_session: AsyncSession,
) -> None:
    with pytest.raises(PasswordTooWeak):
        await register_user(db_session, email="woman@example.com", password="short")

    users = (await db_session.scalars(select(User))).all()
    assert users == []


async def test_register_user_maps_the_email_unique_violation_to_already_registered(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The commit-time race path: the SELECT missed, but the constraint still caught it."""
    monkeypatch.setattr(
        db_session, "commit", AsyncMock(side_effect=_integrity_error("uq_users_email"))
    )

    with pytest.raises(EmailAlreadyRegistered):
        await register_user(db_session, email="woman@example.com", password="correcthorse1")


async def test_register_user_does_not_swallow_an_unrelated_integrity_error(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A constraint violation that is not the email uniqueness one is a real defect."""
    monkeypatch.setattr(
        db_session, "commit", AsyncMock(side_effect=_integrity_error("ck_credentials_kind"))
    )

    with pytest.raises(IntegrityError):
        await register_user(db_session, email="woman@example.com", password="correcthorse1")
