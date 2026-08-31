"""The Accounts tables: a user, her credentials, and her sessions.

Split into separate tables rather than columns on one, because a user has zero
or more ways to prove herself and the split is what makes #11's linking rule
expressible: "the same email address" must never by itself be able to mean
"the same person." ``CredentialKind`` has one member today; a Google
credential (#11) is a new row and a migration adding its own columns, never a
change to what a user *is*.

``Session`` and ``SignInFailure`` arrived with #9. Neither stores a secret
directly — ``Session.refresh_token_hash`` is a digest, the same reasoning
``Credential.password_hash`` is held to — see ``app/accounts/tokens.py``.

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
    Index,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

__all__ = ["Base", "CredentialKind", "User", "Credential", "Session", "SignInFailure"]


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
    sessions: Mapped[list[Session]] = relationship(
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


class Session(Base):
    """A signed-in period. See ``app/accounts/sessions.py`` for the use cases.

    ``refresh_token_hash`` stores ``tokens.hash_refresh_token``'s digest of the
    refresh token, never the token itself — a stolen row cannot be replayed
    as-is. The access token handed out alongside a session is not stored
    anywhere: it is short-lived and deliberately unrevocable, see
    ``app/accounts/tokens.py`` and ``services/backend/CONTEXT.md``.
    """

    __tablename__ = "sessions"
    __table_args__ = (Index("ix_sessions_user_id", "user_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    refresh_token_hash: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    #: Bumped on every successful refresh. IDLE_TIMEOUT (session_policy.py) is
    #: measured from this, not from created_at.
    last_used_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    #: The absolute lifetime (REFRESH_TOKEN_TTL from creation), independent of
    #: how recently the session was used.
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    #: Set once, at sign-out or sign-out-everywhere. Null means still active.
    revoked_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="sessions")


class SignInFailure(Base):
    """One failed sign-in attempt against one (normalised) address.

    What ``app/accounts/sign_in_throttle.py`` counts against to slow repeated
    bad attempts (#9). Rows are not tied to a user — an attempt against an
    address with no account must count the same as one against a real
    account, or the counter itself would reveal which addresses exist.
    """

    __tablename__ = "sign_in_failures"
    __table_args__ = (Index("ix_sign_in_failures_email_created_at", "email", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    email: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
