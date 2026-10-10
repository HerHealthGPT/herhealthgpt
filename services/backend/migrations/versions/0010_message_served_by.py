"""triage: record which reasoning backend actually answered each turn

Revision ID: 0010_message_served_by
Revises: 0009_dob_and_health_note
Create Date: 2026-09-11

``HERHEALTH_TRIAGE_MODE=vllm`` with an OpenRouter key set builds a
``FallbackReasoningClient``: the fine-tuned adapter is tried first and the
base model silently finishes the turn when it fails. Until this column,
nothing recorded which of the two produced the answer — the only trace was a
``logger.warning`` on the server's console, so a finished consultation could
not be attributed afterwards at all.

That matters beyond curiosity. CLAUDE.md holds that the adapter must not
choose an action code until it is retrained on multi-turn data, and any
measurement of how often it answered — or how often it had to be rescued —
needs the per-turn record this column provides.

Nullable, with no backfill. Every row written before this migration is
genuinely unattributable, and writing a guess into them would manufacture
exactly the certainty the column exists to provide honestly.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

#: Kept under 32 characters: alembic_version.version_num is varchar(32), and
#: a longer id fails only at the very end of a successful upgrade.
revision: str = "0010_message_served_by"
down_revision: str | None = "0009_dob_and_health_note"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "messages",
        sa.Column("served_by", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("messages", "served_by")
