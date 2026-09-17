"""The Triage-context tables: a consultation session, and its messages.

Deliberately not in ``app/accounts/models.py`` and not sharing its ``Base`` —
CONTEXT-MAP.md draws a hard line between the Triage and Accounts bounded
contexts, and this project already uses one models module per context. A
``ConsultationSession`` here is *not* issue #13's future "conversation":
that is a separate, Accounts-context, user-facing, encrypted record built
from a *completed* session, added later, and explicitly must never require
a change here (see #13's own acceptance criteria).

``migrations/env.py`` combines this module's metadata with Accounts' for
autogenerate — see that module's own comment.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import TIMESTAMP, CheckConstraint, ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

__all__ = ["Base", "ConsultationSession", "Message"]


class Base(DeclarativeBase):
    pass


class ConsultationSession(Base):
    """One consultation, from its opening message to its conclusion (or not
    yet concluded). ``status`` is a plain text field, not a Postgres enum —
    matching this repo's existing preference (see ``ActionCode`` etc. in
    ``herhealth_contracts``) for enums enforced in the application layer,
    where a CHECK constraint still catches a value the app itself would
    reject.
    """

    __tablename__ = "consultation_sessions"
    __table_args__ = (
        Index("ix_consultation_sessions_user_id", "user_id"),
        CheckConstraint(
            "status IN ('active', 'concluded')", name="ck_consultation_sessions_status"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    #: No FK to app.accounts.models.User on purpose: that would make this
    #: Triage-context module import an Accounts-context one. The column
    #: still enforces referential integrity — see the migration, which adds
    #: the FK constraint directly against the "users" table by name.
    user_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="active")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    #: No ``messages`` relationship on purpose: a lazy-loaded collection
    #: accessed outside SQLAlchemy's async greenlet raises ``MissingGreenlet``
    #: rather than a useful error — caught live writing routes.py. Query
    #: ``Message`` directly, ordered by ``created_at``, the way that module
    #: already does.


class Message(Base):
    """One turn's worth of conversation: her message, or the assistant's.

    ``decision`` holds the full validated ``TriageDecision`` (see
    ``herhealth_contracts.decision``) as JSON, populated only on
    assistant messages — a user message has no decision to store. Storing
    the whole decision, not just ``content``, is what keeps a session's
    citations and action code reconstructable later without re-deriving
    them.
    """

    __tablename__ = "messages"
    __table_args__ = (Index("ix_messages_session_id_created_at", "session_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("consultation_sessions.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    decision: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    #: Which reasoning backend actually answered, and what it took — the
    #: ``{"final": ..., "attempts": [...]}`` shape built by
    #: ``routes._served_by_payload``. Assistant messages only.
    #:
    #: **A column of its own, deliberately not a key inside ``decision``.**
    #: That blob is the validated ``TriageDecision``, whose schema is
    #: ``extra="forbid"``; an extra key in it would break anyone who later
    #: validates a stored decision, and would also imply the model reported
    #: its own identity. This is an observation about the transport, made by
    #: the server, so it is stored beside the decision rather than within it.
    #:
    #: Nullable, and null on every row written before this column existed —
    #: those turns are genuinely unattributable and must not be reported as
    #: anything else.
    served_by: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
