"""The Accounts tables: a user, and the credentials that can prove she is one.

Split into two tables rather than columns on one, because a user has zero or
more ways to prove herself and the split is what makes #11's linking rule
expressible: "the same email address" must never by itself be able to mean
"the same person." ``CredentialKind`` has one member today; a Google
credential (#11) is a new row and a migration adding its own columns, never a
change to what a user *is*.

``Base`` is imported by ``migrations/env.py`` as ``target_metadata`` — see
that module's docstring.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    TIMESTAMP,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

__all__ = ["Base", "CredentialKind", "User", "Credential"]


class Base(DeclarativeBase):
    pass


class CredentialKind(StrEnum):
    """Every way a user may be able to prove herself. Nothing outside this set."""

    PASSWORD = "password"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    #: Normalised via herhealth_backend.app.accounts.emails.normalize_email
    #: before it ever reaches this column.
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    email_verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    credentials: Mapped[list[Credential]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Credential(Base):
    __tablename__ = "credentials"
    __table_args__ = (
        # At most one credential of a given kind per user — one password, later
        # one Google identity. Revisit if a kind ever needs more than one.
        UniqueConstraint("user_id", "kind", name="uq_credentials_user_id_kind"),
        CheckConstraint("kind IN ('password')", name="ck_credentials_kind"),
        CheckConstraint(
            "(kind != 'password') OR (password_hash IS NOT NULL)",
            name="ck_credentials_password_hash_required",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    #: The argon2id hash from herhealth_backend.app.accounts.passwords. Only
    #: set (and only meaningful) when kind is PASSWORD.
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    user: Mapped[User] = relationship(back_populates="credentials")
