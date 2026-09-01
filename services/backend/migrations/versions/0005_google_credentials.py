"""accounts: google credentials

Revision ID: 0005_google_credentials
Revises: 0004_email_verification
Create Date: 2026-09-01

#11's one schema change: ``credentials.kind`` admits ``'google'`` alongside
``'password'``, and a new ``google_subject`` column holds the provider's
stable subject identifier — never the email address, which can change on
the Google side without the account here changing at all. Unique
account-wide, not just per user: a Google identity can only ever prove one
person.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_google_credentials"
down_revision: str | None = "0004_email_verification"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("credentials", sa.Column("google_subject", sa.Text(), nullable=True))
    op.create_unique_constraint(
        "uq_credentials_google_subject", "credentials", ["google_subject"]
    )
    op.drop_constraint("ck_credentials_kind", "credentials", type_="check")
    op.create_check_constraint(
        "ck_credentials_kind", "credentials", "kind IN ('password', 'google')"
    )
    op.create_check_constraint(
        "ck_credentials_google_subject_required",
        "credentials",
        "(kind != 'google') OR (google_subject IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_credentials_google_subject_required", "credentials", type_="check")
    op.drop_constraint("ck_credentials_kind", "credentials", type_="check")
    op.create_check_constraint("ck_credentials_kind", "credentials", "kind IN ('password')")
    op.drop_constraint("uq_credentials_google_subject", "credentials", type_="unique")
    op.drop_column("credentials", "google_subject")
