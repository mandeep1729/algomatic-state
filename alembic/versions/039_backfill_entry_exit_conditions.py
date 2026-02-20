"""Backfill entry/exit conditions in agent_strategies from predefined seed data.

When predefined strategies were migrated to agent_strategies, the entry_long,
entry_short, exit_long, exit_short JSONB columns were left NULL. This migration
populates them with human-readable condition descriptions derived from Go source.

Revision ID: 039
Revises: 038
Create Date: 2026-02-19
"""

import json
import logging

from alembic import op
import sqlalchemy as sa

logger = logging.getLogger(__name__)

revision = "039"
down_revision = "038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from src.trading_agents.predefined import get_predefined_strategies

    conn = op.get_bind()
    updated = 0

    for data in get_predefined_strategies():
        entry_long = data.get("entry_long")
        entry_short = data.get("entry_short")
        exit_long = data.get("exit_long")
        exit_short = data.get("exit_short")

        # Skip strategies that have no entry/exit conditions at all
        if not any([entry_long, entry_short, exit_long, exit_short]):
            continue

        result = conn.execute(
            sa.text("""
                UPDATE agent_strategies
                SET entry_long = :entry_long::jsonb,
                    entry_short = :entry_short::jsonb,
                    exit_long = :exit_long::jsonb,
                    exit_short = :exit_short::jsonb,
                    updated_at = NOW()
                WHERE is_predefined = TRUE
                  AND source_strategy_id = :sid
            """),
            {
                "entry_long": json.dumps(entry_long) if entry_long else None,
                "entry_short": json.dumps(entry_short) if entry_short else None,
                "exit_long": json.dumps(exit_long) if exit_long else None,
                "exit_short": json.dumps(exit_short) if exit_short else None,
                "sid": data["source_strategy_id"],
            },
        )
        updated += result.rowcount

    logger.info("Backfilled entry/exit conditions for %d predefined strategies", updated)


def downgrade() -> None:
    conn = op.get_bind()
    result = conn.execute(
        sa.text("""
            UPDATE agent_strategies
            SET entry_long = NULL,
                entry_short = NULL,
                exit_long = NULL,
                exit_short = NULL,
                updated_at = NOW()
            WHERE is_predefined = TRUE
        """)
    )
    logger.info("Cleared entry/exit conditions for %d predefined strategies", result.rowcount)
