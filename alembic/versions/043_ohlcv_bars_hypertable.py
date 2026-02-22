"""Convert ohlcv_bars to a TimescaleDB hypertable.

Enables automatic time-based partitioning for the highest-volume table.
This migration:
1. Drops the FK from computed_features.bar_id (hypertables cannot be FK targets)
2. Drops the single-column PK on ohlcv_bars(id)
3. Creates a composite PK on (id, timestamp) — required by TimescaleDB
4. Converts ohlcv_bars to a hypertable with 7-day chunks

The downgrade raises NotImplementedError — hypertable conversion is one-way.
Rollback is via Docker volume backup restore.

Revision ID: 043
Revises: 042
Create Date: 2026-02-21
"""

from alembic import op

revision = "043"
down_revision = "042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Drop FK from computed_features.bar_id -> ohlcv_bars.id
    #    Hypertables cannot be the target of foreign keys.
    #    The UNIQUE constraint on bar_id is preserved for ON CONFLICT usage.
    op.drop_constraint(
        "computed_features_bar_id_fkey", "computed_features", type_="foreignkey"
    )

    # 2. Drop the single-column PK on ohlcv_bars(id)
    #    TimescaleDB requires the partitioning column in all unique constraints.
    op.drop_constraint("ohlcv_bars_pkey", "ohlcv_bars", type_="primary")

    # 3. Create composite PK on (id, timestamp)
    op.create_primary_key("ohlcv_bars_pkey", "ohlcv_bars", ["id", "timestamp"])

    # 4. Convert to hypertable with 7-day chunk interval
    #    migrate_data => true moves existing rows into time-based chunks.
    op.execute(
        "SELECT create_hypertable('ohlcv_bars', 'timestamp', "
        "migrate_data => true, chunk_time_interval => INTERVAL '7 days')"
    )


def downgrade() -> None:
    raise NotImplementedError(
        "Hypertable conversion is irreversible. "
        "Restore from the pre-migration Docker volume backup."
    )
