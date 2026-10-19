"""accounts: files she chose to keep, deleted after 30 days

Revision ID: 0012_stored_files
Revises: 0011_cycle_data
Create Date: 2026-10-19

The bytes live on the server's disk; this table is what is known about
them. Many per user; removed with her account by ON DELETE CASCADE, and
when past expires_at by the backend's clean-up. See ADR 0020.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012_stored_files"
down_revision: str | None = "0011_cycle_data"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "stored_files",
        # Set by the application: the file is written under it first.
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("content_type", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.Text(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
    )
    op.create_index("ix_stored_files_user_id", "stored_files", ["user_id"])
    op.create_index("ix_stored_files_expires_at", "stored_files", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_stored_files_expires_at", table_name="stored_files")
    op.drop_index("ix_stored_files_user_id", table_name="stored_files")
    op.drop_table("stored_files")
