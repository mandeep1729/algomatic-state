"""Create TimescaleDB continuous aggregates for 5Min, 15Min, 1Hour timeframes.

Replaces manual Go aggregation with automatic TimescaleDB continuous aggregates.
This migration:
1. Deletes existing aggregated rows for 5Min, 15Min, 1Hour from ohlcv_bars
2. Creates continuous aggregate materialized views for each timeframe
3. Adds automatic refresh policies
4. Runs initial refresh to populate historical data

The initial refresh uses a raw DBAPI connection with autocommit because
refresh_continuous_aggregate() cannot run inside a transaction block.

The downgrade drops the views and refresh policies.

Revision ID: 044
Revises: 043
Create Date: 2026-02-22
"""

from alembic import op

revision = "044"
down_revision = "043"
branch_labels = None
depends_on = None

VIEWS = ["ohlcv_bars_5min", "ohlcv_bars_15min", "ohlcv_bars_1hour"]


def upgrade() -> None:
    # 1. Delete existing manually-aggregated rows.
    #    These will be replaced by continuous aggregate views.
    op.execute(
        "DELETE FROM ohlcv_bars WHERE timeframe IN ('5Min', '15Min', '1Hour')"
    )

    # 2. Create continuous aggregate for 5Min bars.
    op.execute("""
        CREATE MATERIALIZED VIEW ohlcv_bars_5min
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket('5 minutes', timestamp) AS bucket,
            ticker_id,
            first(open, timestamp) AS open,
            max(high) AS high,
            min(low) AS low,
            last(close, timestamp) AS close,
            sum(volume) AS volume,
            sum(trade_count) AS trade_count
        FROM ohlcv_bars
        WHERE timeframe = '1Min'
        GROUP BY time_bucket('5 minutes', timestamp), ticker_id
        WITH NO DATA
    """)

    # 3. Create continuous aggregate for 15Min bars.
    op.execute("""
        CREATE MATERIALIZED VIEW ohlcv_bars_15min
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket('15 minutes', timestamp) AS bucket,
            ticker_id,
            first(open, timestamp) AS open,
            max(high) AS high,
            min(low) AS low,
            last(close, timestamp) AS close,
            sum(volume) AS volume,
            sum(trade_count) AS trade_count
        FROM ohlcv_bars
        WHERE timeframe = '1Min'
        GROUP BY time_bucket('15 minutes', timestamp), ticker_id
        WITH NO DATA
    """)

    # 4. Create continuous aggregate for 1Hour bars.
    op.execute("""
        CREATE MATERIALIZED VIEW ohlcv_bars_1hour
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket('1 hour', timestamp) AS bucket,
            ticker_id,
            first(open, timestamp) AS open,
            max(high) AS high,
            min(low) AS low,
            last(close, timestamp) AS close,
            sum(volume) AS volume,
            sum(trade_count) AS trade_count
        FROM ohlcv_bars
        WHERE timeframe = '1Min'
        GROUP BY time_bucket('1 hour', timestamp), ticker_id
        WITH NO DATA
    """)

    # 5. Add refresh policies.
    #    - start_offset: how far back to refresh on each run
    #    - end_offset: exclude recent incomplete buckets
    #    - schedule_interval: how often the policy runs
    op.execute("""
        SELECT add_continuous_aggregate_policy('ohlcv_bars_5min',
            start_offset => INTERVAL '1 hour',
            end_offset => INTERVAL '5 minutes',
            schedule_interval => INTERVAL '5 minutes')
    """)

    op.execute("""
        SELECT add_continuous_aggregate_policy('ohlcv_bars_15min',
            start_offset => INTERVAL '2 hours',
            end_offset => INTERVAL '15 minutes',
            schedule_interval => INTERVAL '15 minutes')
    """)

    op.execute("""
        SELECT add_continuous_aggregate_policy('ohlcv_bars_1hour',
            start_offset => INTERVAL '6 hours',
            end_offset => INTERVAL '1 hour',
            schedule_interval => INTERVAL '30 minutes')
    """)

    # 6. Initial refresh to materialize all existing historical data.
    #    refresh_continuous_aggregate() cannot run inside a transaction,
    #    so we commit the DDL first and use autocommit for the refresh calls.
    bind = op.get_bind()
    dbapi_conn = bind.connection.dbapi_connection
    dbapi_conn.commit()
    dbapi_conn.autocommit = True
    try:
        cursor = dbapi_conn.cursor()
        for view in VIEWS:
            cursor.execute(
                f"CALL refresh_continuous_aggregate('{view}', NULL, localtimestamp)"
            )
        cursor.close()
    finally:
        dbapi_conn.autocommit = False
        dbapi_conn.cursor().execute("BEGIN")


def downgrade() -> None:
    # Remove refresh policies first, then drop views.
    op.execute(
        "SELECT remove_continuous_aggregate_policy('ohlcv_bars_1hour', if_exists => true)"
    )
    op.execute(
        "SELECT remove_continuous_aggregate_policy('ohlcv_bars_15min', if_exists => true)"
    )
    op.execute(
        "SELECT remove_continuous_aggregate_policy('ohlcv_bars_5min', if_exists => true)"
    )

    op.execute("DROP MATERIALIZED VIEW IF EXISTS ohlcv_bars_1hour CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ohlcv_bars_15min CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ohlcv_bars_5min CASCADE")
