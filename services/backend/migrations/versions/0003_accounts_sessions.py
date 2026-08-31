"""accounts: sessions and sign-in failures

Revision ID: 0003_accounts_sessions
Revises: 0002_accounts_tables
Create Date: 2026-08-31

#9's two tables. ``sessions`` holds one row per signed-in refresh token —
never the token itself, only ``tokens.hash_refresh_token``'s digest of it,
the same reasoning ``credentials.password_hash`` is held to. ``sign_in_failures``
is what ``sign_in_throttle.py`` counts against to slow repeated bad sign-ins
for one address; rows are cleared on the next successful sign-in rather than
on a timer, so the lockout window (see ``session_policy.py``) is enforced by
the query that reads them, not by a cleanup job.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_accounts_sessions"
down_revision: str | None = "0002_accounts_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sessions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("refresh_token_hash", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "last_used_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.UniqueConstraint("refresh_token_hash", name="uq_sessions_refresh_token_hash"),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])

    op.create_table(
        "sign_in_failures",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_sign_in_failures_email_created_at", "sign_in_failures", ["email", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_sign_in_failures_email_created_at", table_name="sign_in_failures")
    op.drop_table("sign_in_failures")
    op.drop_index("ix_sessions_user_id", table_name="sessions")
    op.drop_table("sessions")
