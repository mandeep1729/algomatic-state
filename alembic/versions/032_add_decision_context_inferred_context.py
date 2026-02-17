"""Add inferred_context column to decision_contexts table.

Stores structured context about the trade decision inferred by the system,
such as market regime, volatility state, and other contextual signals that
were active at the time of the trade.

Revision ID: 032
Revises: 031
Create Date: 2026-02-16
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers
revision = "032"
down_revision = "031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "decision_contexts",
        sa.Column("inferred_context", JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("decision_contexts", "inferred_context")
