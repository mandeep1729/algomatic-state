"""Consolidate ohlcv_states into computed_features table.

This migration:
1. Adds state columns to computed_features (model_id, state_id, state_prob, log_likelihood)
2. Migrates existing data from ohlcv_states to computed_features
3. Drops the ohlcv_states table

Revision ID: 004
Revises: 003
Create Date: 2026-01-28 22:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add state columns to computed_features and drop ohlcv_states table."""
    # 1. Add state columns to computed_features
    with op.batch_alter_table("computed_features") as batch_op:
        batch_op.add_column(sa.Column("model_id", sa.String(50), nullable=True))
        batch_op.add_column(sa.Column("state_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("state_prob", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("log_likelihood", sa.Float(), nullable=True))

    # 2. Create indexes for state queries
    op.create_index("ix_features_model_id", "computed_features", ["model_id"])
    op.create_index("ix_features_model_state", "computed_features", ["model_id", "state_id"])

    # 3. Add check constraint for state_prob
    op.create_check_constraint(
        "ck_state_prob_range",
        "computed_features",
        "state_prob IS NULL OR (state_prob >= 0 AND state_prob <= 1)"
    )

    # 4. Migrate data from ohlcv_states to computed_features
    # Update computed_features rows that have matching bar_id in ohlcv_states
    op.execute("""
        UPDATE computed_features cf
        SET
            model_id = os.model_id,
            state_id = os.state_id,
            state_prob = os.state_prob,
            log_likelihood = os.log_likelihood
        FROM ohlcv_states os
        WHERE cf.bar_id = os.bar_id
    """)

    # 5. Drop ohlcv_states table
    op.drop_table("ohlcv_states")


def downgrade() -> None:
    """Recreate ohlcv_states table and move state data back."""
    # 1. Recreate ohlcv_states table
    op.create_table(
        "ohlcv_states",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("bar_id", sa.BigInteger(), nullable=False),
        sa.Column("model_id", sa.String(50), nullable=False),
        sa.Column("state_id", sa.Integer(), nullable=False),
        sa.Column("state_prob", sa.Float(), nullable=False),
        sa.Column("log_likelihood", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["bar_id"], ["ohlcv_bars.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("bar_id", "model_id", name="uq_ohlcv_states_bar_model"),
        sa.CheckConstraint("state_prob >= 0 AND state_prob <= 1", name="ck_ohlcv_state_prob_range"),
    )
    op.create_index("ix_ohlcv_states_bar_id", "ohlcv_states", ["bar_id"])
    op.create_index("ix_ohlcv_states_model_id", "ohlcv_states", ["model_id"])
    op.create_index("ix_ohlcv_states_state_id", "ohlcv_states", ["state_id"])

    # 2. Migrate data back from computed_features to ohlcv_states
    op.execute("""
        INSERT INTO ohlcv_states (bar_id, model_id, state_id, state_prob, log_likelihood)
        SELECT bar_id, model_id, state_id, state_prob, log_likelihood
        FROM computed_features
        WHERE model_id IS NOT NULL AND state_id IS NOT NULL
    """)

    # 3. Remove state columns from computed_features
    op.drop_constraint("ck_state_prob_range", "computed_features", type_="check")
    op.drop_index("ix_features_model_state", "computed_features")
    op.drop_index("ix_features_model_id", "computed_features")

    with op.batch_alter_table("computed_features") as batch_op:
        batch_op.drop_column("log_likelihood")
        batch_op.drop_column("state_prob")
        batch_op.drop_column("state_id")
        batch_op.drop_column("model_id")
