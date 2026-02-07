"""Add risk_profile JSONB column to strategies table.

Allows per-strategy risk overrides that take precedence over the user's
default risk_profile from user_profiles during trade evaluation.

Revision ID: 012
Revises: 011
Create Date: 2026-02-07
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "strategies",
        sa.Column("risk_profile", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("strategies", "risk_profile")
