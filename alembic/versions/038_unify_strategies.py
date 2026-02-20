"""Unify strategies into agent_strategies table.

Extends agent_strategies with columns from the strategies table (timeframes,
max_risk_pct, min_risk_reward, risk_profile, tags), migrates existing rows,
updates the fill_decisions FK, and drops the strategies table.

Revision ID: 038
Revises: 037
Create Date: 2026-02-19
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "038"
down_revision = "037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1a. Add new columns to agent_strategies
    op.add_column("agent_strategies", sa.Column("timeframes", JSONB, nullable=True))
    op.add_column("agent_strategies", sa.Column("max_risk_pct", sa.Float, nullable=True))
    op.add_column("agent_strategies", sa.Column("min_risk_reward", sa.Float, nullable=True))
    op.add_column("agent_strategies", sa.Column("risk_profile", JSONB, nullable=True))
    op.add_column("agent_strategies", sa.Column("tags", JSONB, nullable=True))

    # 1b. Migrate strategies rows → agent_strategies
    conn = op.get_bind()

    # Check if the strategies table exists before attempting migration
    inspector = sa.inspect(conn)
    if "strategies" in inspector.get_table_names():
        old_rows = conn.execute(sa.text("SELECT * FROM strategies")).fetchall()

        # Build old→new ID mapping for FK update
        id_mapping = {}
        for row in old_rows:
            row_dict = row._mapping

            # Map direction: 'both' -> 'long_short', 'long' -> 'long_only', 'short' -> 'short_only'
            old_dir = row_dict.get("direction") or "both"
            direction_map = {"both": "long_short", "long": "long_only", "short": "short_only"}
            direction = direction_map.get(old_dir, "long_short")

            # Map implied_strategy_family to category, default to 'custom'
            category = row_dict.get("implied_strategy_family") or "custom"

            # Map entry/exit criteria to JSONB (store as JSON string)
            entry_criteria = row_dict.get("entry_criteria")
            exit_criteria = row_dict.get("exit_criteria")

            result = conn.execute(
                sa.text("""
                    INSERT INTO agent_strategies
                        (account_id, name, display_name, description, category, direction,
                         entry_long, exit_long, timeframes, max_risk_pct, min_risk_reward,
                         risk_profile, is_predefined, is_active, created_at, updated_at)
                    VALUES
                        (:account_id, :name, :display_name, :description, :category, :direction,
                         :entry_long, :exit_long, :timeframes, :max_risk_pct, :min_risk_reward,
                         :risk_profile, FALSE, :is_active, :created_at, :updated_at)
                    RETURNING id
                """),
                {
                    "account_id": row_dict["account_id"],
                    "name": row_dict["name"],
                    "display_name": row_dict["name"],  # strategies didn't have display_name
                    "description": row_dict.get("description"),
                    "category": category,
                    "direction": direction,
                    "entry_long": f'"{entry_criteria}"' if entry_criteria else None,
                    "exit_long": f'"{exit_criteria}"' if exit_criteria else None,
                    "timeframes": sa.type_coerce(row_dict.get("timeframes"), JSONB),
                    "max_risk_pct": row_dict.get("max_risk_pct"),
                    "min_risk_reward": row_dict.get("min_risk_reward"),
                    "risk_profile": sa.type_coerce(row_dict.get("risk_profile"), JSONB),
                    "is_active": row_dict.get("is_active", True),
                    "created_at": row_dict.get("created_at"),
                    "updated_at": row_dict.get("updated_at"),
                },
            )
            new_id = result.fetchone()[0]
            id_mapping[row_dict["id"]] = new_id

        # 1c. Update decision_contexts.strategy_id FK using old→new ID mapping
        for old_id, new_id in id_mapping.items():
            conn.execute(
                sa.text(
                    "UPDATE decision_contexts SET strategy_id = :new_id WHERE strategy_id = :old_id"
                ),
                {"old_id": old_id, "new_id": new_id},
            )

        # Drop FK constraint on decision_contexts.strategy_id → strategies.id
        op.drop_constraint(
            "decision_contexts_strategy_id_fkey",
            "decision_contexts",
            type_="foreignkey",
        )

        # Add FK constraint on decision_contexts.strategy_id → agent_strategies.id
        op.create_foreign_key(
            "decision_contexts_strategy_id_fkey",
            "decision_contexts",
            "agent_strategies",
            ["strategy_id"],
            ["id"],
            ondelete="SET NULL",
        )

        # 1d. Drop strategies table
        op.drop_table("strategies")


def downgrade() -> None:
    # Recreate strategies table
    op.create_table(
        "strategies",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("account_id", sa.Integer, sa.ForeignKey("user_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("direction", sa.String(10), nullable=True, default="both"),
        sa.Column("timeframes", JSONB, nullable=True),
        sa.Column("entry_criteria", sa.Text, nullable=True),
        sa.Column("exit_criteria", sa.Text, nullable=True),
        sa.Column("max_risk_pct", sa.Float, nullable=True),
        sa.Column("min_risk_reward", sa.Float, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, default=True),
        sa.Column("risk_profile", JSONB, nullable=True),
        sa.Column("implied_strategy_family", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("account_id", "name", name="uq_strategy_account_name"),
    )

    # Revert FK on decision_contexts
    op.drop_constraint(
        "decision_contexts_strategy_id_fkey",
        "decision_contexts",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "decision_contexts_strategy_id_fkey",
        "decision_contexts",
        "strategies",
        ["strategy_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Drop new columns from agent_strategies
    op.drop_column("agent_strategies", "tags")
    op.drop_column("agent_strategies", "risk_profile")
    op.drop_column("agent_strategies", "min_risk_reward")
    op.drop_column("agent_strategies", "max_risk_pct")
    op.drop_column("agent_strategies", "timeframes")
