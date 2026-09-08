"""accounts: date of birth on users, and an optional health note beside them

Revision ID: 0009_dob_and_health_note
Revises: 0008_user_display_name
Create Date: 2026-09-06

Two columns' worth of change, deliberately in two different places — see
ADR 0015. ``users.date_of_birth`` is demographic, the same kind of thing as
``email`` and ``display_name``, so it sits on the user. The free-text note is
what she chooses to tell us about her health, and
``services/backend/CONTEXT.md`` says a User holds "nothing clinical", so it
gets its own table that can be dropped without touching her account.

``date_of_birth`` is nullable even though the product treats it as mandatory:
accounts created before this migration have no date to backfill, and inventing
one would be worse than recording that we do not know. New sign-ups are
required to supply it by the API, not by the column.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

#: Kept under 32 characters: alembic_version.version_num is varchar(32), and
#: a longer id fails only at the very end of a successful upgrade.
revision: str = "0009_dob_and_health_note"
down_revision: str | None = "0008_user_display_name"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("date_of_birth", sa.Date(), nullable=True))

    op.create_table(
        "health_notes",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        # Unique, not just indexed: one note per user, edited in place. A
        # second row would mean two answers to "what has she told us".
        sa.Column(
            "user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_table("health_notes")
    op.drop_column("users", "date_of_birth")
