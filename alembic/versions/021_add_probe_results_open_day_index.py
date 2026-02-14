"""Add standalone index on strategy_probe_results.open_day.

Multiple API queries filter by open_day date range without other leading
columns.  The existing composite unique constraint starts with run_id,
so it cannot serve these range scans efficiently.

Revision ID: 021
Revises: 020
Create Date: 2026-02-13
"""

from alembic import op

# revision identifiers
revision = "021"
down_revision = "020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_probe_results_open_day",
        "strategy_probe_results",
        ["open_day"],
    )


def downgrade() -> None:
    op.drop_index("ix_probe_results_open_day", table_name="strategy_probe_results")
