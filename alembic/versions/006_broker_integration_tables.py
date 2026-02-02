"""Add SnapTrade broker integration tables.

This migration adds tables for SnapTrade broker integration:
- snaptrade_users: Mapping between internal users and SnapTrade users
- broker_connections: Connected brokerage accounts
- trade_histories: Historical trades synced from brokers

Revision ID: 006
Revises: 005
Create Date: 2026-02-01 22:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create SnapTrade broker integration tables."""
    # 1. Create snaptrade_users table
    op.create_table(
        "snaptrade_users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_account_id", sa.Integer(), nullable=False),
        sa.Column("snaptrade_user_id", sa.String(255), nullable=False),
        sa.Column("snaptrade_user_secret", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_account_id"], ["user_accounts.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_account_id", name="uq_snaptrade_users_account"),
        sa.UniqueConstraint("snaptrade_user_id", name="uq_snaptrade_users_snap_id"),
    )
    op.create_index("ix_snaptrade_users_account_id", "snaptrade_users", ["user_account_id"])

    # 2. Create broker_connections table
    op.create_table(
        "broker_connections",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("snaptrade_user_id", sa.Integer(), nullable=False),
        sa.Column("brokerage_name", sa.String(100), nullable=False),
        sa.Column("brokerage_slug", sa.String(50), nullable=False),
        sa.Column("authorization_id", sa.String(255), nullable=False),
        sa.Column("meta", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["snaptrade_user_id"], ["snaptrade_users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("authorization_id", name="uq_broker_connections_auth_id"),
    )
    op.create_index("ix_broker_connections_snaptrade_user_id", "broker_connections", ["snaptrade_user_id"])
    op.create_index("ix_broker_connections_brokerage_slug", "broker_connections", ["brokerage_slug"])

    # 3. Create trade_histories table
    op.create_table(
        "trade_histories",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("broker_connection_id", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("side", sa.String(10), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("fees", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("external_trade_id", sa.String(255), nullable=True),
        sa.Column("raw_data", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["broker_connection_id"], ["broker_connections.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("external_trade_id", name="uq_trade_histories_external_id"),
    )
    op.create_index("ix_trade_histories_symbol", "trade_histories", ["symbol"])
    op.create_index("ix_trade_histories_executed_at", "trade_histories", ["executed_at"])
    op.create_index("ix_trade_histories_connection_symbol", "trade_histories", ["broker_connection_id", "symbol"])


def downgrade() -> None:
    """Drop SnapTrade broker integration tables."""
    op.drop_table("trade_histories")
    op.drop_table("broker_connections")
    op.drop_table("snaptrade_users")
