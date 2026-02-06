"""Trade lifecycle schema: evolve trade_histories → trade_fills and add position tracking.

This migration:
1. Renames trade_histories → trade_fills
2. Adds new columns to trade_fills (account_id, broker, asset_type, etc.)
3. Backfills account_id and broker from existing data
4. Creates position_lots, lot_closures, round_trips tables
5. Renames existing indexes

Revision ID: 008
Revises: 007
Create Date: 2026-02-06 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -------------------------------------------------------------------------
    # Step 1: Rename trade_histories → trade_fills
    # -------------------------------------------------------------------------
    op.rename_table("trade_histories", "trade_fills")

    # -------------------------------------------------------------------------
    # Step 2: Add new columns to trade_fills
    # -------------------------------------------------------------------------
    op.add_column(
        "trade_fills",
        sa.Column(
            "account_id",
            sa.Integer(),
            sa.ForeignKey("user_accounts.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "trade_fills",
        sa.Column("broker", sa.String(100), nullable=True),
    )
    op.add_column(
        "trade_fills",
        sa.Column("asset_type", sa.String(20), nullable=True),
    )
    op.add_column(
        "trade_fills",
        sa.Column("currency", sa.String(10), nullable=False, server_default="USD"),
    )
    op.add_column(
        "trade_fills",
        sa.Column("order_id", sa.String(255), nullable=True),
    )
    op.add_column(
        "trade_fills",
        sa.Column("venue", sa.String(100), nullable=True),
    )
    op.add_column(
        "trade_fills",
        sa.Column("import_batch_id", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "trade_fills",
        sa.Column(
            "intent_id",
            sa.BigInteger(),
            sa.ForeignKey("trade_intents.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # -------------------------------------------------------------------------
    # Step 3: Backfill account_id and broker from existing relationships
    # broker_connections → snaptrade_users → user_accounts
    # -------------------------------------------------------------------------
    op.execute("""
        UPDATE trade_fills tf
        SET account_id = su.user_account_id,
            broker = bc.brokerage_name
        FROM broker_connections bc
        JOIN snaptrade_users su ON bc.snaptrade_user_id = su.id
        WHERE tf.broker_connection_id = bc.id
    """)

    # -------------------------------------------------------------------------
    # Step 4: Add constraints and indexes on trade_fills
    # -------------------------------------------------------------------------
    op.create_check_constraint(
        "ck_trade_fill_side",
        "trade_fills",
        "side IN ('buy', 'sell')",
    )
    op.create_unique_constraint(
        "uq_trade_fill_account_external_id",
        "trade_fills",
        ["account_id", "external_trade_id"],
    )
    op.create_index(
        "ix_trade_fills_account_symbol",
        "trade_fills",
        ["account_id", "symbol"],
    )

    # Rename old indexes to match new table name
    # The table rename carries indexes but their names still reference the old table
    op.execute("ALTER INDEX IF EXISTS ix_trade_histories_symbol RENAME TO ix_trade_fills_symbol")
    op.execute("ALTER INDEX IF EXISTS ix_trade_histories_executed_at RENAME TO ix_trade_fills_executed_at")
    op.execute(
        "ALTER INDEX IF EXISTS ix_trade_histories_connection_symbol "
        "RENAME TO ix_trade_fills_connection_symbol"
    )
    op.execute(
        "ALTER INDEX IF EXISTS trade_histories_external_trade_id_key "
        "RENAME TO trade_fills_external_trade_id_key"
    )

    # -------------------------------------------------------------------------
    # Step 5: Create position_lots table
    # -------------------------------------------------------------------------
    op.create_table(
        "position_lots",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column(
            "account_id",
            sa.Integer(),
            sa.ForeignKey("user_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "open_fill_id",
            sa.BigInteger(),
            sa.ForeignKey("trade_fills.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("open_qty", sa.Float(), nullable=False),
        sa.Column("remaining_qty", sa.Float(), nullable=False),
        sa.Column("avg_open_price", sa.Float(), nullable=False),
        sa.Column("strategy_tag", sa.String(100), nullable=True),
        sa.Column("status", sa.String(10), nullable=False, server_default="open"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        # Constraints
        sa.CheckConstraint("direction IN ('long', 'short')", name="ck_lot_direction"),
        sa.CheckConstraint("open_qty > 0", name="ck_lot_open_qty_positive"),
        sa.CheckConstraint("remaining_qty >= 0", name="ck_lot_remaining_qty_nonneg"),
        sa.CheckConstraint("avg_open_price > 0", name="ck_lot_avg_price_positive"),
        sa.CheckConstraint("status IN ('open', 'closed')", name="ck_lot_status"),
    )
    op.create_index("ix_position_lots_symbol", "position_lots", ["symbol"])
    op.create_index("ix_position_lots_status", "position_lots", ["status"])
    op.create_index(
        "ix_position_lots_account_symbol_status",
        "position_lots",
        ["account_id", "symbol", "status"],
    )

    # -------------------------------------------------------------------------
    # Step 6: Create lot_closures table
    # -------------------------------------------------------------------------
    op.create_table(
        "lot_closures",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column(
            "lot_id",
            sa.BigInteger(),
            sa.ForeignKey("position_lots.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "open_fill_id",
            sa.BigInteger(),
            sa.ForeignKey("trade_fills.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "close_fill_id",
            sa.BigInteger(),
            sa.ForeignKey("trade_fills.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("matched_qty", sa.Float(), nullable=False),
        sa.Column("open_price", sa.Float(), nullable=False),
        sa.Column("close_price", sa.Float(), nullable=False),
        sa.Column("realized_pnl", sa.Float(), nullable=True),
        sa.Column("fees_allocated", sa.Float(), nullable=True),
        sa.Column("match_method", sa.String(10), nullable=False, server_default="fifo"),
        sa.Column(
            "matched_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        # Constraints
        sa.CheckConstraint("matched_qty > 0", name="ck_closure_qty_positive"),
        sa.CheckConstraint("open_price > 0", name="ck_closure_open_price_positive"),
        sa.CheckConstraint("close_price > 0", name="ck_closure_close_price_positive"),
        sa.CheckConstraint(
            "match_method IN ('fifo', 'lifo', 'avg', 'manual')",
            name="ck_closure_match_method",
        ),
    )
    op.create_index("ix_lot_closures_lot_id", "lot_closures", ["lot_id"])
    op.create_index("ix_lot_closures_close_fill_id", "lot_closures", ["close_fill_id"])

    # -------------------------------------------------------------------------
    # Step 7: Create round_trips table
    # -------------------------------------------------------------------------
    op.create_table(
        "round_trips",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column(
            "account_id",
            sa.Integer(),
            sa.ForeignKey("user_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("qty_opened", sa.Float(), nullable=True),
        sa.Column("qty_closed", sa.Float(), nullable=True),
        sa.Column("avg_open_price", sa.Float(), nullable=True),
        sa.Column("avg_close_price", sa.Float(), nullable=True),
        sa.Column("realized_pnl", sa.Float(), nullable=True),
        sa.Column("return_pct", sa.Float(), nullable=True),
        sa.Column("holding_period_sec", sa.Integer(), nullable=True),
        sa.Column("num_fills", sa.Integer(), nullable=True),
        sa.Column("tags", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("derived_from", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        # Constraints
        sa.CheckConstraint("direction IN ('long', 'short')", name="ck_rt_direction"),
    )
    op.create_index("ix_round_trips_symbol", "round_trips", ["symbol"])
    op.create_index("ix_round_trips_account_symbol", "round_trips", ["account_id", "symbol"])
    op.create_index("ix_round_trips_account_closed", "round_trips", ["account_id", "closed_at"])


def downgrade() -> None:
    # -------------------------------------------------------------------------
    # Reverse Step 7: Drop round_trips
    # -------------------------------------------------------------------------
    op.drop_table("round_trips")

    # -------------------------------------------------------------------------
    # Reverse Step 6: Drop lot_closures
    # -------------------------------------------------------------------------
    op.drop_table("lot_closures")

    # -------------------------------------------------------------------------
    # Reverse Step 5: Drop position_lots
    # -------------------------------------------------------------------------
    op.drop_table("position_lots")

    # -------------------------------------------------------------------------
    # Reverse Step 4: Drop new constraints and indexes on trade_fills
    # -------------------------------------------------------------------------
    op.execute("ALTER INDEX IF EXISTS ix_trade_fills_symbol RENAME TO ix_trade_histories_symbol")
    op.execute("ALTER INDEX IF EXISTS ix_trade_fills_executed_at RENAME TO ix_trade_histories_executed_at")
    op.execute(
        "ALTER INDEX IF EXISTS ix_trade_fills_connection_symbol "
        "RENAME TO ix_trade_histories_connection_symbol"
    )
    op.execute(
        "ALTER INDEX IF EXISTS trade_fills_external_trade_id_key "
        "RENAME TO trade_histories_external_trade_id_key"
    )

    op.drop_index("ix_trade_fills_account_symbol", table_name="trade_fills")
    op.drop_constraint("uq_trade_fill_account_external_id", "trade_fills", type_="unique")
    op.drop_constraint("ck_trade_fill_side", "trade_fills", type_="check")

    # -------------------------------------------------------------------------
    # Reverse Step 2: Drop new columns from trade_fills
    # -------------------------------------------------------------------------
    op.drop_column("trade_fills", "intent_id")
    op.drop_column("trade_fills", "import_batch_id")
    op.drop_column("trade_fills", "venue")
    op.drop_column("trade_fills", "order_id")
    op.drop_column("trade_fills", "currency")
    op.drop_column("trade_fills", "asset_type")
    op.drop_column("trade_fills", "broker")
    op.drop_column("trade_fills", "account_id")

    # -------------------------------------------------------------------------
    # Reverse Step 1: Rename trade_fills → trade_histories
    # -------------------------------------------------------------------------
    op.rename_table("trade_fills", "trade_histories")
