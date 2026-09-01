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

``EmailVerificationCode`` and ``VerificationCodeSend`` arrived with #10, same
reasoning again: ``code_hash`` is a keyed digest (see
``app/accounts/verification_codes.py``), never the code itself.

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

__all__ = [
    "Base",
    "CredentialKind",
    "User",
    "Credential",
    "Session",
    "SignInFailure",
    "EmailVerificationCode",
    "VerificationCodeSend",
]


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
    verification_code: Mapped[EmailVerificationCode | None] = relationship(
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


class EmailVerificationCode(Base):
    """The one active verification code for a user. See ``app/accounts/email_verification.py``.

    One row per user, not one row per code issued: requesting a new code
    (resend) overwrites this row rather than adding another, so there is
    never more than one code that can succeed at a time — a superseded code
    simply stops existing rather than needing a separate flag to say so.
    ``code_hash`` is a keyed digest (``verification_codes.hash_code``); the
    plaintext code lives only in memory, long enough to email it.
    """

    __tablename__ = "email_verification_codes"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    code_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    #: Wrong guesses against this code. MAX_ATTEMPTS (verification_code_policy.py)
    #: invalidates the code entirely once reached — a new one must be requested.
    attempts: Mapped[int] = mapped_column(nullable=False, server_default=text("0"))
    #: Set once, on successful verification. Null means not yet used — checked
    #: so the same code cannot be replayed after it has already verified the address.
    used_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="verification_code")


class VerificationCodeSend(Base):
    """One verification code sent to one (normalised) address.

    What ``app/accounts/verification_send_throttle.py`` counts against to
    limit how often a fresh code can be requested (#10) — kept by address
    like ``SignInFailure``, and for the same reason: a resend request against
    an address with no account must count identically to one against a real
    account, or the counter itself would out which addresses are registered.
    """

    __tablename__ = "verification_code_sends"
    __table_args__ = (Index("ix_verification_code_sends_email_created_at", "email", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    email: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
