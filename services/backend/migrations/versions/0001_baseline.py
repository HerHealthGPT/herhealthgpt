"""baseline: establish migration tracking before the first table

Revision ID: 0001_baseline
Revises:
Create Date: 2026-08-12

The walking skeleton has no tables of its own — the health check only asks the
database ``SELECT 1``. This revision exists so migration versioning is in place
from the first commit rather than retrofitted: applying it creates Alembic's
``alembic_version`` bookkeeping and nothing else. The first real schema (users,
credentials, sessions) is a revision that lists this one as its parent.
"""

from __future__ import annotations

from collections.abc import Sequence

revision: str = "0001_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
