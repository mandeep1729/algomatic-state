"""Enable TimescaleDB extension.

TimescaleDB is a PostgreSQL extension for time-series data. Enabling it
is a prerequisite for converting tables to hypertables.

Revision ID: 042
Revises: 041
Create Date: 2026-02-21
"""

from alembic import op

revision = "042"
down_revision = "041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS timescaledb CASCADE")
