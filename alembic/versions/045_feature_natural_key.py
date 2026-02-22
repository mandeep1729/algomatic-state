"""Switch computed_features conflict resolution from bar_id to natural key.

Migration 044 introduced TimescaleDB continuous aggregates for 5Min, 15Min,
and 1Hour timeframes. These views return id=0 for all rows (virtual
aggregations, not stored rows), which breaks the bar_id-based unique
constraint and conflict resolution in computed_features.

This migration:
1. Makes bar_id nullable (aggregate timeframes have no real bar row)
2. Drops the existing UNIQUE constraint on bar_id
3. Replaces the non-unique index ix_features_ticker_timeframe_ts with
   a UNIQUE constraint on (ticker_id, timeframe, timestamp)
4. Sets bar_id = NULL for orphaned rows referencing deleted aggregated bars
5. Cleans up stale data_sync_log entries for aggregate timeframes

Revision ID: 045
Revises: 044
Create Date: 2026-02-21
"""

from alembic import op

revision = "045"
down_revision = "044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Make bar_id nullable — aggregate timeframes have no real bar row.
    op.alter_column("computed_features", "bar_id", nullable=True)

    # 2. Drop the old UNIQUE constraint on bar_id.
    #    (Created in migration 002 as "uq_features_bar_id")
    op.drop_constraint("computed_features_bar_id_key", "computed_features", type_="unique")

    # 3. Remove duplicate rows that would violate the new unique constraint.
    #    Keep only the row with the highest id for each (ticker_id, timeframe, timestamp).
    #    Uses a CTE with window function for efficiency on large tables.
    op.execute("""
        DELETE FROM computed_features
        WHERE id IN (
            SELECT id FROM (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY ticker_id, timeframe, timestamp
                           ORDER BY id DESC
                       ) AS rn
                FROM computed_features
            ) ranked
            WHERE rn > 1
        )
    """)

    # 4. Drop the existing non-unique index on (ticker_id, timeframe, timestamp)
    #    and recreate it as a UNIQUE constraint.
    op.drop_index("ix_features_ticker_timeframe_ts", "computed_features")
    op.create_unique_constraint(
        "uq_features_ticker_timeframe_ts",
        "computed_features",
        ["ticker_id", "timeframe", "timestamp"],
    )

    # 4. Set bar_id = NULL for orphaned rows whose bar_id no longer exists
    #    in ohlcv_bars (e.g. deleted 5Min/15Min/1Hour aggregated rows).
    op.execute("""
        UPDATE computed_features cf
        SET bar_id = NULL
        WHERE cf.bar_id IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM ohlcv_bars ob WHERE ob.id = cf.bar_id
          )
    """)

    # 5. Clean up stale data_sync_log entries for aggregate timeframes.
    #    Manual aggregation no longer exists — these are now continuous aggregates.
    op.execute(
        "DELETE FROM data_sync_log WHERE timeframe IN ('5Min', '15Min', '1Hour')"
    )


def downgrade() -> None:
    # Set orphaned NULLs back to 0 so the NOT NULL constraint can be restored.
    op.execute("UPDATE computed_features SET bar_id = 0 WHERE bar_id IS NULL")

    # Drop the natural-key unique constraint and restore the non-unique index.
    op.drop_constraint(
        "uq_features_ticker_timeframe_ts", "computed_features", type_="unique"
    )
    op.create_index(
        "ix_features_ticker_timeframe_ts",
        "computed_features",
        ["ticker_id", "timeframe", "timestamp"],
    )

    # Restore the UNIQUE constraint on bar_id.
    op.create_unique_constraint(
        "computed_features_bar_id_key", "computed_features", ["bar_id"]
    )

    # Restore NOT NULL on bar_id.
    op.alter_column("computed_features", "bar_id", nullable=False)
