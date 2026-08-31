"""accounts: users and credentials

Revision ID: 0002_accounts_tables
Revises: 0001_baseline
Create Date: 2026-08-31

The first real Accounts tables (#8). ``users`` holds nothing but an address
and a verification flag; ``credentials`` holds the ways she can prove she is
that user, one row per way. Splitting them lets #11's Google credential arrive
as a new row and a follow-up migration adding its own nullable columns,
never as a change to what a user is.

Both primary keys default to ``gen_random_uuid()``, a core PostgreSQL 13+
function — no extension to install, no Python-side default that could drift
across processes.

The revision id is kept short deliberately: Alembic's own bookkeeping table,
``alembic_version.version_num``, is a ``varchar(32)`` unless a migration
widens it, and a longer id fails on upgrade rather than at review time.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_accounts_tables"
down_revision: str | None = "0001_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column(
            "email_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    op.create_table(
        "credentials",
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
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("user_id", "kind", name="uq_credentials_user_id_kind"),
        sa.CheckConstraint("kind IN ('password')", name="ck_credentials_kind"),
        sa.CheckConstraint(
            "(kind != 'password') OR (password_hash IS NOT NULL)",
            name="ck_credentials_password_hash_required",
        ),
    )


def downgrade() -> None:
    op.drop_table("credentials")
    op.drop_table("users")
