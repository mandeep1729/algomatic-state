"""Drop campaigns table, make campaign_fills self-contained.

The campaigns table is a thin wrapper storing (id, account_id, symbol, strategy_id)
— all derivable from fills + decision_contexts. The rebuild logic already computes
campaign groupings from fills using FIFO zero-crossing, so campaigns adds no
information. We replace campaign_fills with a self-contained table using group_id
(first fill_id in the group) as the deterministic campaign identifier.

Revision ID: 027
Revises: 026
Create Date: 2026-02-16
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision = "027"
down_revision = "026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Drop campaign_fills (has FK to campaigns)
    op.drop_table("campaign_fills")

    # 2. Drop campaigns table
    op.drop_table("campaigns")

    # 3. Create new self-contained campaign_fills
    op.create_table(
        "campaign_fills",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("group_id", sa.BigInteger, nullable=False),
        sa.Column(
            "fill_id",
            sa.BigInteger,
            sa.ForeignKey("trade_fills.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("group_id", "fill_id", name="uq_campaign_fills_group_fill"),
        sa.Index("ix_campaign_fills_group_id", "group_id"),
        sa.Index("ix_campaign_fills_fill_id", "fill_id"),
    )


def downgrade() -> None:
    # 1. Drop new campaign_fills
    op.drop_table("campaign_fills")

    # 2. Recreate campaigns table
    op.create_table(
        "campaigns",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "account_id",
            sa.Integer,
            sa.ForeignKey("user_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column(
            "strategy_id",
            sa.Integer,
            sa.ForeignKey("strategies.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Index(
            "ix_campaigns_account_symbol_strategy",
            "account_id",
            "symbol",
            "strategy_id",
        ),
    )

    # 3. Recreate old campaign_fills junction table
    op.create_table(
        "campaign_fills",
        sa.Column(
            "campaign_id",
            sa.BigInteger,
            sa.ForeignKey("campaigns.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "fill_id",
            sa.BigInteger,
            sa.ForeignKey("trade_fills.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )
