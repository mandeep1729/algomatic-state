"""Split user_accounts into auth/personal + trading profile tables.

This migration:
1. Creates user_profiles table
2. Copies existing risk/trading data from user_accounts to user_profiles
3. Drops risk columns and check constraints from user_accounts
4. Adds auth/personal columns to user_accounts (google_id, auth_provider, etc.)
5. Makes email non-null + unique on user_accounts

Revision ID: 007
Revises: 006
Create Date: 2026-02-04 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Step 1: Create user_profiles table ---
    op.create_table(
        "user_profiles",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column(
            "user_account_id",
            sa.Integer(),
            sa.ForeignKey("user_accounts.id", ondelete="CASCADE"),
            unique=True,
            nullable=False,
        ),
        sa.Column("account_balance", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("max_position_size_pct", sa.Float(), nullable=False, server_default="5.0"),
        sa.Column("max_risk_per_trade_pct", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("max_daily_loss_pct", sa.Float(), nullable=False, server_default="3.0"),
        sa.Column("min_risk_reward_ratio", sa.Float(), nullable=False, server_default="2.0"),
        sa.Column(
            "default_timeframes",
            postgresql.JSONB(),
            nullable=False,
            server_default='["1Min", "5Min", "15Min", "1Hour"]',
        ),
        sa.Column("experience_level", sa.String(50), nullable=True),
        sa.Column("trading_style", sa.String(50), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("account_balance >= 0", name="ck_profile_balance_positive"),
        sa.CheckConstraint(
            "max_position_size_pct > 0 AND max_position_size_pct <= 100",
            name="ck_profile_max_position_pct_range",
        ),
        sa.CheckConstraint(
            "max_risk_per_trade_pct > 0 AND max_risk_per_trade_pct <= 100",
            name="ck_profile_max_risk_pct_range",
        ),
        sa.CheckConstraint(
            "max_daily_loss_pct > 0 AND max_daily_loss_pct <= 100",
            name="ck_profile_max_daily_loss_range",
        ),
        sa.CheckConstraint("min_risk_reward_ratio > 0", name="ck_profile_min_rr_positive"),
    )

    # --- Step 2: Copy existing risk data from user_accounts → user_profiles ---
    op.execute("""
        INSERT INTO user_profiles (user_account_id, account_balance, max_position_size_pct,
                                   max_risk_per_trade_pct, max_daily_loss_pct,
                                   min_risk_reward_ratio, default_timeframes,
                                   created_at, updated_at)
        SELECT id, account_balance, max_position_size_pct,
               max_risk_per_trade_pct, max_daily_loss_pct,
               min_risk_reward_ratio, default_timeframes,
               created_at, updated_at
        FROM user_accounts
    """)

    # --- Step 3: Drop risk columns and check constraints from user_accounts ---
    # Drop check constraints first
    op.drop_constraint("ck_account_balance_positive", "user_accounts", type_="check")
    op.drop_constraint("ck_max_position_pct_range", "user_accounts", type_="check")
    op.drop_constraint("ck_max_risk_pct_range", "user_accounts", type_="check")
    op.drop_constraint("ck_max_daily_loss_range", "user_accounts", type_="check")
    op.drop_constraint("ck_min_rr_positive", "user_accounts", type_="check")

    # Drop columns
    op.drop_column("user_accounts", "account_balance")
    op.drop_column("user_accounts", "max_position_size_pct")
    op.drop_column("user_accounts", "max_risk_per_trade_pct")
    op.drop_column("user_accounts", "max_daily_loss_pct")
    op.drop_column("user_accounts", "min_risk_reward_ratio")
    op.drop_column("user_accounts", "default_timeframes")

    # --- Step 4: Add auth/personal columns to user_accounts ---
    op.add_column(
        "user_accounts",
        sa.Column("google_id", sa.String(255), unique=True, nullable=True),
    )
    op.add_column(
        "user_accounts",
        sa.Column("auth_provider", sa.String(50), nullable=False, server_default="google"),
    )
    op.add_column(
        "user_accounts",
        sa.Column("profile_picture_url", sa.String(1024), nullable=True),
    )
    op.add_column(
        "user_accounts",
        sa.Column("phone", sa.String(50), nullable=True),
    )
    op.add_column(
        "user_accounts",
        sa.Column("address", sa.Text(), nullable=True),
    )
    op.add_column(
        "user_accounts",
        sa.Column("date_of_birth", sa.Date(), nullable=True),
    )
    op.add_column(
        "user_accounts",
        sa.Column("gender", sa.String(20), nullable=True),
    )

    # --- Step 5: Make email non-null + unique ---
    # First, fill any NULL emails with a placeholder based on external_user_id
    op.execute("""
        UPDATE user_accounts
        SET email = external_user_id || '@placeholder.local'
        WHERE email IS NULL
    """)
    op.alter_column("user_accounts", "email", nullable=False)
    op.create_unique_constraint("uq_user_accounts_email", "user_accounts", ["email"])


def downgrade() -> None:
    # --- Reverse Step 5: Remove unique constraint, allow NULL emails ---
    op.drop_constraint("uq_user_accounts_email", "user_accounts", type_="unique")
    op.alter_column("user_accounts", "email", nullable=True)

    # --- Reverse Step 4: Drop auth/personal columns ---
    op.drop_column("user_accounts", "gender")
    op.drop_column("user_accounts", "date_of_birth")
    op.drop_column("user_accounts", "address")
    op.drop_column("user_accounts", "phone")
    op.drop_column("user_accounts", "profile_picture_url")
    op.drop_column("user_accounts", "auth_provider")
    op.drop_column("user_accounts", "google_id")

    # --- Reverse Step 3: Re-add risk columns with defaults ---
    op.add_column(
        "user_accounts",
        sa.Column("account_balance", sa.Float(), nullable=False, server_default="0.0"),
    )
    op.add_column(
        "user_accounts",
        sa.Column("max_position_size_pct", sa.Float(), nullable=False, server_default="5.0"),
    )
    op.add_column(
        "user_accounts",
        sa.Column("max_risk_per_trade_pct", sa.Float(), nullable=False, server_default="1.0"),
    )
    op.add_column(
        "user_accounts",
        sa.Column("max_daily_loss_pct", sa.Float(), nullable=False, server_default="3.0"),
    )
    op.add_column(
        "user_accounts",
        sa.Column("min_risk_reward_ratio", sa.Float(), nullable=False, server_default="2.0"),
    )
    op.add_column(
        "user_accounts",
        sa.Column(
            "default_timeframes",
            postgresql.JSONB(),
            nullable=False,
            server_default='["1Min", "5Min", "15Min", "1Hour"]',
        ),
    )

    # Re-add check constraints
    op.create_check_constraint("ck_account_balance_positive", "user_accounts", "account_balance >= 0")
    op.create_check_constraint(
        "ck_max_position_pct_range",
        "user_accounts",
        "max_position_size_pct > 0 AND max_position_size_pct <= 100",
    )
    op.create_check_constraint(
        "ck_max_risk_pct_range",
        "user_accounts",
        "max_risk_per_trade_pct > 0 AND max_risk_per_trade_pct <= 100",
    )
    op.create_check_constraint(
        "ck_max_daily_loss_range",
        "user_accounts",
        "max_daily_loss_pct > 0 AND max_daily_loss_pct <= 100",
    )
    op.create_check_constraint("ck_min_rr_positive", "user_accounts", "min_risk_reward_ratio > 0")

    # --- Reverse Step 2: Copy data back from user_profiles → user_accounts ---
    op.execute("""
        UPDATE user_accounts ua
        SET account_balance = up.account_balance,
            max_position_size_pct = up.max_position_size_pct,
            max_risk_per_trade_pct = up.max_risk_per_trade_pct,
            max_daily_loss_pct = up.max_daily_loss_pct,
            min_risk_reward_ratio = up.min_risk_reward_ratio,
            default_timeframes = up.default_timeframes
        FROM user_profiles up
        WHERE ua.id = up.user_account_id
    """)

    # --- Reverse Step 1: Drop user_profiles table ---
    op.drop_table("user_profiles")
