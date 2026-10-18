"""accounts: cycle data she imported, one row per user

Revision ID: 0011_cycle_data
Revises: 0010_message_served_by
Create Date: 2026-10-18

Beside the user, not on her, for the reason ``health_notes`` is (ADR 0015):
it is clinical, and it must be deletable without closing her account. Holds
the confirmed extraction only, never the uploaded file. See ADR 0019.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011_cycle_data"
down_revision: str | None = "0010_message_served_by"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cycle_data",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        # Unique: one import per user, replaced on the next.
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("extraction", postgresql.JSONB(), nullable=False),
        sa.Column(
            "confirmed_no_period_pain",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "imported_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_table("cycle_data")
