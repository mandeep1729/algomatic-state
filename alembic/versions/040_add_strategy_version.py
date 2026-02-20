"""Add version column to agent_strategies for cache invalidation.

The Go agent-service caches compiled strategy definitions in memory.
This version column allows the resolver to detect when a strategy's
conditions have been updated and recompile from the JSONB DSL.

Revision ID: 040
Revises: 039
Create Date: 2026-02-20
"""

from alembic import op
import sqlalchemy as sa

revision = "040"
down_revision = "039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agent_strategies",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )


def downgrade() -> None:
    op.drop_column("agent_strategies", "version")
