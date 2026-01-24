"""Remove vwap from ohlcv_bars.

Revision ID: 003
Revises: 002
Create Date: 2024-01-23 01:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop vwap column from ohlcv_bars."""
    # Use batch_alter_table for SQLite compatibility if needed, though we use Postgres
    with op.batch_alter_table("ohlcv_bars") as batch_op:
        batch_op.drop_column("vwap")


def downgrade() -> None:
    """Add vwap column back to ohlcv_bars."""
    with op.batch_alter_table("ohlcv_bars") as batch_op:
        batch_op.add_column(sa.Column("vwap", sa.Float(), nullable=True))
