"""accounts: password reset codes and sends

Revision ID: 0006_password_reset
Revises: 0005_google_credentials
Create Date: 2026-09-01

#12's two tables, shaped exactly like 0004's ``email_verification_codes`` and
``verification_code_sends``. ``password_reset_codes`` holds one row per
user — a fresh request overwrites it rather than adding a new row, so at
most one code can ever succeed at a time. ``code_hash`` is a keyed digest
(``password_reset_codes.hash_code``), never the code itself.
``password_reset_sends`` is an append-only log ``password_reset_throttle.py``
counts against to limit how often a reset can be requested for one address.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_password_reset"
down_revision: str | None = "0005_google_credentials"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "password_reset_codes",
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
        sa.UniqueConstraint("user_id", name="uq_password_reset_codes_user_id"),
    )

    op.create_table(
        "password_reset_sends",
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
        "ix_password_reset_sends_email_created_at",
        "password_reset_sends",
        ["email", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_password_reset_sends_email_created_at", table_name="password_reset_sends")
    op.drop_table("password_reset_sends")
    op.drop_table("password_reset_codes")
