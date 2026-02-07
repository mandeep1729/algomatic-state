"""Add strategy config columns and journal entries table.

This migration:
1. Adds strategy config columns (direction, timeframes, entry_criteria,
   exit_criteria, max_risk_pct, min_risk_reward)
2. Creates journal_entries table

Note: user_profiles settings (max_open_positions, stop_loss_required,
primary_markets, account_size_range, evaluation_controls) are now stored
in the profile/risk_profile JSONB columns added in migration 011.

Revision ID: 013
Revises: 012
Create Date: 2026-02-07
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers
revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. strategies: add config columns
    op.add_column(
        "strategies",
        sa.Column("direction", sa.String(10), server_default="both", nullable=True),
    )
    op.add_column(
        "strategies",
        sa.Column("timeframes", JSONB, nullable=True),
    )
    op.add_column(
        "strategies",
        sa.Column("entry_criteria", sa.Text(), nullable=True),
    )
    op.add_column(
        "strategies",
        sa.Column("exit_criteria", sa.Text(), nullable=True),
    )
    op.add_column(
        "strategies",
        sa.Column("max_risk_pct", sa.Float(), server_default="2.0", nullable=True),
    )
    op.add_column(
        "strategies",
        sa.Column("min_risk_reward", sa.Float(), server_default="1.5", nullable=True),
    )

    # 2. Create journal_entries table
    op.create_table(
        "journal_entries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("date", sa.String(10), nullable=False),
        sa.Column("entry_type", sa.String(30), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("trade_id", sa.String(50), nullable=True),
        sa.Column("tags", JSONB, nullable=True),
        sa.Column("mood", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["account_id"], ["user_accounts.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_journal_entries_account_id", "journal_entries", ["account_id"])
    op.create_index("ix_journal_entries_date", "journal_entries", ["date"])
    op.create_index("ix_journal_entries_account_date", "journal_entries", ["account_id", "date"])


def downgrade() -> None:
    # 2. Drop journal_entries table
    op.drop_index("ix_journal_entries_account_date", table_name="journal_entries")
    op.drop_index("ix_journal_entries_date", table_name="journal_entries")
    op.drop_index("ix_journal_entries_account_id", table_name="journal_entries")
    op.drop_table("journal_entries")

    # 1. strategies: drop config columns
    op.drop_column("strategies", "min_risk_reward")
    op.drop_column("strategies", "max_risk_pct")
    op.drop_column("strategies", "exit_criteria")
    op.drop_column("strategies", "entry_criteria")
    op.drop_column("strategies", "timeframes")
    op.drop_column("strategies", "direction")
