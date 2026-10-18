"""The Accounts tables: a user, her credentials, and her sessions.

Split into separate tables rather than columns on one, because a user has zero
or more ways to prove herself and the split is what makes #11's linking rule
expressible: "the same email address" must never by itself be able to mean
"the same person." ``CredentialKind.GOOGLE`` (#11) is a new row and a
migration adding its own columns, never a change to what a user *is*.

``Session`` and ``SignInFailure`` arrived with #9. Neither stores a secret
directly — ``Session.refresh_token_hash`` is a digest, the same reasoning
``Credential.password_hash`` is held to — see ``app/accounts/tokens.py``.

``EmailVerificationCode`` and ``VerificationCodeSend`` arrived with #10, same
reasoning again: ``code_hash`` is a keyed digest (see
``app/accounts/verification_codes.py``), never the code itself.

``PasswordResetCode`` and ``PasswordResetSend`` arrived with #12, mirroring
those two tables exactly for the same reasons — see
``app/accounts/password_reset.py``.

``Base`` is imported by ``migrations/env.py`` as ``target_metadata`` — see
that module's docstring.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import (
    TIMESTAMP,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

__all__ = [
    "Base",
    "CredentialKind",
    "User",
    "Credential",
    "CycleData",
    "HealthNote",
    "Session",
    "SignInFailure",
    "EmailVerificationCode",
    "VerificationCodeSend",
    "PasswordResetCode",
    "PasswordResetSend",
]


class Base(DeclarativeBase):
    pass


class CredentialKind(StrEnum):
    """Every way a user may be able to prove herself. Nothing outside this set."""

    PASSWORD = "password"
    GOOGLE = "google"


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
    #: How she wants to be greeted in the UI. Optional — never her login id.
    display_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: Demographic, not clinical, which is why it belongs on the user at all
    #: (see HealthNote for the part that does not). Stored as a date rather
    #: than an age band so it cannot go stale: age crosses 45 on a birthday,
    #: and knowledge/features.yaml records that 45 is what separates
    #: perimenopause from PCOS. The band is derived at read time — see
    #: herhealth_backend.triage.age_bands.
    #:
    #: Nullable, though the product asks every new sign-up for it: accounts
    #: that predate migration 0009 have no date, and a placeholder would be a
    #: fact we invented. Absent means unknown and is handled as unknown.
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
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
    password_reset_code: Mapped[PasswordResetCode | None] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    health_note: Mapped[HealthNote | None] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    cycle_data: Mapped[CycleData | None] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class HealthNote(Base):
    """Anything a user chooses to tell us about her health once, so she does
    not have to repeat it at the start of every consultation. Optional.

    Its own table rather than a column on ``User`` because
    ``services/backend/CONTEXT.md`` defines a user as holding "an email
    address and nothing clinical — everything she reports lives in a
    conversation, not on her". This is the exception that glossary now
    records (ADR 0015), and keeping it separate is what makes it true: the
    note can be deleted on its own, the way that glossary already describes
    optional cycle data, without closing her account.

    One row per user, edited in place — the same shape as
    ``EmailVerificationCode``, for a related reason: two rows would mean two
    answers to "what has she told us", and nothing would say which is
    current.

    **Not a medical record, and the word is avoided deliberately.** It is
    unverified free text she typed, it is never treated as a symptom she is
    reporting today, and it can never fire a red flag — see
    ``herhealth_backend.app.triage.routes`` for how it reaches the model.

    ``content`` is stored in plaintext, like ``messages.content``. The
    application-layer encryption ``CONTEXT.md`` records as settled is not
    built yet; this column inherits that gap rather than introducing it, and
    ADR 0015's risk register says so.
    """

    __tablename__ = "health_notes"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
        onupdate=text("now()"),
    )

    user: Mapped[User] = relationship(back_populates="health_note")


class CycleData(Base):
    """Cycle data she imported from a tracking app and confirmed. Optional.

    The same shape as ``HealthNote``, for the same reasons: its own table so
    it can be deleted without closing her account (the **Cycle data** term in
    ``services/backend/CONTEXT.md``), and one row per user replaced on every
    import, so there is never a question of which import is current.

    ``extraction`` is a ``herhealth_contracts.cycle.CycleExtraction`` as JSON
    — closed-vocabulary values and dates only, never the uploaded file, which
    is not kept. It is re-validated against that schema whenever it is read.
    Stored in plaintext like ``health_notes.content``; ADR 0019's risk
    register says so.
    """

    __tablename__ = "cycle_data"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    extraction: Mapped[dict] = mapped_column(JSONB, nullable=False)
    #: She answered "Yes, no pain" in the import preview. Her own statement,
    #: the only way an absence in her logs can answer a feature.
    confirmed_no_period_pain: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    imported_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    user: Mapped[User] = relationship(back_populates="cycle_data")


class Credential(Base):
    __tablename__ = "credentials"
    __table_args__ = (
        # At most one credential of a given kind per user — one password, one
        # Google identity. Revisit if a kind ever needs more than one.
        UniqueConstraint("user_id", "kind", name="uq_credentials_user_id_kind"),
        # A Google subject identifies at most one credential account-wide —
        # unlike password_hash, this is not per-user data, it is the join key
        # #11 uses instead of email (email_verified.py's docstring on why:
        # addresses change, Google's `sub` does not).
        UniqueConstraint("google_subject", name="uq_credentials_google_subject"),
        CheckConstraint("kind IN ('password', 'google')", name="ck_credentials_kind"),
        CheckConstraint(
            "(kind != 'password') OR (password_hash IS NOT NULL)",
            name="ck_credentials_password_hash_required",
        ),
        CheckConstraint(
            "(kind != 'google') OR (google_subject IS NOT NULL)",
            name="ck_credentials_google_subject_required",
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
    #: Google's stable `sub` claim. Only set (and only meaningful) when kind
    #: is GOOGLE — see app/accounts/google_identity.py. Unique across every
    #: user, not just this one, because a Google identity can only ever
    #: prove one person.
    google_subject: Mapped[str | None] = mapped_column(Text, nullable=True)
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


class PasswordResetCode(Base):
    """The one active password-reset code for a user. See ``app/accounts/password_reset.py``.

    Shaped exactly like ``EmailVerificationCode``, for the same reason: one
    row per user, overwritten rather than added to on a fresh request, so at
    most one code can ever succeed at a time. ``code_hash`` is a keyed digest
    (``password_reset_codes.hash_code``); the plaintext code lives only in
    memory, long enough to email it.
    """

    __tablename__ = "password_reset_codes"

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
    #: Wrong guesses against this code. MAX_ATTEMPTS (password_reset_policy.py)
    #: invalidates the code entirely once reached — a new one must be requested.
    attempts: Mapped[int] = mapped_column(nullable=False, server_default=text("0"))
    #: Set once, on a successful reset. Null means not yet used — checked so
    #: the same code cannot be replayed to reset the password a second time.
    used_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="password_reset_code")


class PasswordResetSend(Base):
    """One password-reset code sent to one (normalised) address.

    What ``app/accounts/password_reset_throttle.py`` counts against to limit
    how often a reset can be requested (#12) — kept by address like
    ``VerificationCodeSend``, and for the same reason: a request against an
    address with no account, or one with no password credential, must count
    identically to a real, successful request, or the counter itself would
    reveal something about the address.
    """

    __tablename__ = "password_reset_sends"
    __table_args__ = (Index("ix_password_reset_sends_email_created_at", "email", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    email: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
