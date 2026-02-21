"""Convert predefined strategy conditions from text to executable DSL JSON.

Updates all predefined agent_strategies rows with DSL condition arrays
that the Go DSL compiler can parse and compile into ConditionFn closures.
Also bumps the version column to invalidate the resolver cache.

Revision ID: 041
Revises: 040
Create Date: 2026-02-21
"""

import json
import logging

from alembic import op
import sqlalchemy as sa

logger = logging.getLogger(__name__)

revision = "041"
down_revision = "040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Import predefined strategies with DSL JSON conditions.
    from src.trading_agents.predefined import get_predefined_strategies

    strategies = get_predefined_strategies()

    conn = op.get_bind()
    updated = 0

    for s in strategies:
        source_id = s["source_strategy_id"]
        entry_long = json.dumps(s.get("entry_long")) if s.get("entry_long") else None
        entry_short = json.dumps(s.get("entry_short")) if s.get("entry_short") else None
        exit_long = json.dumps(s.get("exit_long")) if s.get("exit_long") else None
        exit_short = json.dumps(s.get("exit_short")) if s.get("exit_short") else None

        result = conn.execute(
            sa.text(
                """
                UPDATE agent_strategies
                SET entry_long = CAST(:entry_long AS jsonb),
                    entry_short = CAST(:entry_short AS jsonb),
                    exit_long = CAST(:exit_long AS jsonb),
                    exit_short = CAST(:exit_short AS jsonb),
                    version = version + 1
                WHERE is_predefined = true
                  AND source_strategy_id = :source_id
                """
            ),
            {
                "entry_long": entry_long,
                "entry_short": entry_short,
                "exit_long": exit_long,
                "exit_short": exit_short,
                "source_id": source_id,
            },
        )
        if result.rowcount > 0:
            updated += 1

    logger.info("Updated %d predefined strategies with DSL JSON conditions", updated)


def downgrade() -> None:
    # No practical downgrade — the text descriptions are lost.
    # Decrement version to allow cache re-sync.
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE agent_strategies
            SET version = version + 1
            WHERE is_predefined = true
            """
        )
    )
