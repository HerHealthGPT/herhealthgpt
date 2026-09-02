"""accounts: optional display name on users

Revision ID: 0008_user_display_name
Revises: 0006_password_reset
Create Date: 2026-09-02

Lets signed-in users choose how their name appears in the app without
exposing account metadata on the public dashboard.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_user_display_name"
down_revision: str | None = "0006_password_reset"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("display_name", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "display_name")
