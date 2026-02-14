"""Drop strategy_id from position_campaigns.

Campaign strategy is inferred from its underlying legs' DecisionContexts,
not stored independently. The denormalized column caused bugs in
unwind_legs_after() when broker-synced campaigns had strategy_id=NULL.

Revision ID: 023
Revises: 022
Create Date: 2026-02-14
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision = "023"
down_revision = "022"
branch_labels = None
depends_on = None


def _get_fk_name(table: str, column: str, referred_table: str) -> str:
    """Look up the actual FK constraint name from the database."""
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            """
            SELECT con.conname
            FROM pg_constraint con
            JOIN pg_attribute att ON att.attnum = ANY(con.conkey)
                AND att.attrelid = con.conrelid
            WHERE con.conrelid = CAST(:table AS regclass)
                AND att.attname = :column
                AND con.contype = 'f'
                AND con.confrelid = CAST(:referred AS regclass)
            """
        ),
        {"table": table, "column": column, "referred": referred_table},
    )
    row = result.fetchone()
    if not row:
        raise RuntimeError(
            f"FK constraint not found: {table}.{column} -> {referred_table}"
        )
    return row[0]


def upgrade() -> None:
    # Drop FK constraint then column
    fk_name = _get_fk_name("position_campaigns", "strategy_id", "strategies")
    op.drop_constraint(fk_name, "position_campaigns", type_="foreignkey")
    op.drop_column("position_campaigns", "strategy_id")


def downgrade() -> None:
    # Re-add the column with FK
    op.add_column(
        "position_campaigns",
        sa.Column(
            "strategy_id",
            sa.Integer(),
            sa.ForeignKey("strategies.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
