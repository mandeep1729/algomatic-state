"""Change open_day from Integer to Date in strategy_probe_results.

The open_day column previously stored day-of-week as an integer (0-6).
This migration changes it to a proper Date type to store the full
calendar date (YYYY-MM-DD), eliminating ambiguity when trades span
multiple months or years.

Existing data is truncated because integer weekday values cannot be
meaningfully converted to dates. The table is cleared before the
column type change.

Revision ID: 018
Revises: 017
Create Date: 2026-02-08
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Clear existing probe results and trades (cascade) since integer
    # weekday values cannot be converted to meaningful dates.
    op.execute("DELETE FROM strategy_probe_results")

    # Drop the unique constraint that references open_day
    op.drop_constraint("uq_probe_result_dimensions", "strategy_probe_results", type_="unique")

    # Change column type from Integer to Date
    op.alter_column(
        "strategy_probe_results",
        "open_day",
        existing_type=sa.Integer(),
        type_=sa.Date(),
        existing_nullable=False,
        postgresql_using="NULL",
    )

    # Recreate the unique constraint with the new column type
    op.create_unique_constraint(
        "uq_probe_result_dimensions",
        "strategy_probe_results",
        ["run_id", "symbol", "strategy_id", "timeframe", "risk_profile",
         "open_day", "open_hour", "long_short"],
    )


def downgrade() -> None:
    # Clear data since date values cannot be converted back to weekday integers
    op.execute("DELETE FROM strategy_probe_results")

    op.drop_constraint("uq_probe_result_dimensions", "strategy_probe_results", type_="unique")

    op.alter_column(
        "strategy_probe_results",
        "open_day",
        existing_type=sa.Date(),
        type_=sa.Integer(),
        existing_nullable=False,
        postgresql_using="NULL",
    )

    op.create_unique_constraint(
        "uq_probe_result_dimensions",
        "strategy_probe_results",
        ["run_id", "symbol", "strategy_id", "timeframe", "risk_profile",
         "open_day", "open_hour", "long_short"],
    )
