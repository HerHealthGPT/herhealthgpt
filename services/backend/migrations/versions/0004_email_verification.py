"""accounts: email verification codes and sends

Revision ID: 0004_email_verification
Revises: 0003_accounts_sessions
Create Date: 2026-09-01

#10's two tables. ``email_verification_codes`` holds one row per user — a
resend overwrites it rather than adding a new row, so at most one code can
ever succeed at a time. ``code_hash`` is a keyed digest
(``verification_codes.hash_code``), never the code itself, the same
reasoning ``sessions.refresh_token_hash`` is held to. ``verification_code_sends``
is an append-only log ``verification_send_throttle.py`` counts against to
limit how often a fresh code can be requested for one address.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_email_verification"
down_revision: str | None = "0003_accounts_sessions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "email_verification_codes",
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
        sa.Column("code_hash", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("used_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.UniqueConstraint("user_id", name="uq_email_verification_codes_user_id"),
    )

    op.create_table(
        "verification_code_sends",
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
        "ix_verification_code_sends_email_created_at",
        "verification_code_sends",
        ["email", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_verification_code_sends_email_created_at", table_name="verification_code_sends"
    )
    op.drop_table("verification_code_sends")
    op.drop_table("email_verification_codes")
