"""Consolidate user_profiles columns into profile and risk_profile JSONB.

This migration:
1. Adds profile (JSONB) and risk_profile (JSONB) columns
2. Copies existing column data into the new JSONB columns
3. Drops old individual columns and their CHECK constraints

Revision ID: 011
Revises: 010
Create Date: 2026-02-07
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Step 1: Add new JSONB columns ---
    op.add_column(
        "user_profiles",
        sa.Column(
            "profile",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text(
                """'{"account_balance": 0.0, "default_timeframes": ["1Min", "5Min", "15Min", "1Hour"], "experience_level": null, "trading_style": null}'::jsonb"""
            ),
        ),
    )
    op.add_column(
        "user_profiles",
        sa.Column(
            "risk_profile",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text(
                """'{"max_position_size_pct": 5.0, "max_risk_per_trade_pct": 1.0, "max_daily_loss_pct": 3.0, "min_risk_reward_ratio": 2.0}'::jsonb"""
            ),
        ),
    )

    # --- Step 2: Copy existing data into the JSONB columns ---
    op.execute("""
        UPDATE user_profiles
        SET profile = jsonb_build_object(
                'account_balance', account_balance,
                'default_timeframes', default_timeframes,
                'experience_level', experience_level,
                'trading_style', trading_style
            ),
            risk_profile = jsonb_build_object(
                'max_position_size_pct', max_position_size_pct,
                'max_risk_per_trade_pct', max_risk_per_trade_pct,
                'max_daily_loss_pct', max_daily_loss_pct,
                'min_risk_reward_ratio', min_risk_reward_ratio
            )
    """)

    # --- Step 3: Drop CHECK constraints ---
    op.drop_constraint("ck_profile_balance_positive", "user_profiles", type_="check")
    op.drop_constraint("ck_profile_max_position_pct_range", "user_profiles", type_="check")
    op.drop_constraint("ck_profile_max_risk_pct_range", "user_profiles", type_="check")
    op.drop_constraint("ck_profile_max_daily_loss_range", "user_profiles", type_="check")
    op.drop_constraint("ck_profile_min_rr_positive", "user_profiles", type_="check")

    # --- Step 4: Drop old columns ---
    op.drop_column("user_profiles", "account_balance")
    op.drop_column("user_profiles", "max_position_size_pct")
    op.drop_column("user_profiles", "max_risk_per_trade_pct")
    op.drop_column("user_profiles", "max_daily_loss_pct")
    op.drop_column("user_profiles", "min_risk_reward_ratio")
    op.drop_column("user_profiles", "default_timeframes")
    op.drop_column("user_profiles", "experience_level")
    op.drop_column("user_profiles", "trading_style")


def downgrade() -> None:
    # --- Step 1: Re-add old columns with defaults ---
    op.add_column(
        "user_profiles",
        sa.Column("account_balance", sa.Float(), nullable=False, server_default="0.0"),
    )
    op.add_column(
        "user_profiles",
        sa.Column("max_position_size_pct", sa.Float(), nullable=False, server_default="5.0"),
    )
    op.add_column(
        "user_profiles",
        sa.Column("max_risk_per_trade_pct", sa.Float(), nullable=False, server_default="1.0"),
    )
    op.add_column(
        "user_profiles",
        sa.Column("max_daily_loss_pct", sa.Float(), nullable=False, server_default="3.0"),
    )
    op.add_column(
        "user_profiles",
        sa.Column("min_risk_reward_ratio", sa.Float(), nullable=False, server_default="2.0"),
    )
    op.add_column(
        "user_profiles",
        sa.Column(
            "default_timeframes",
            postgresql.JSONB(),
            nullable=False,
            server_default='["1Min", "5Min", "15Min", "1Hour"]',
        ),
    )
    op.add_column(
        "user_profiles",
        sa.Column("experience_level", sa.String(50), nullable=True),
    )
    op.add_column(
        "user_profiles",
        sa.Column("trading_style", sa.String(50), nullable=True),
    )

    # --- Step 2: Copy data back from JSONB columns ---
    op.execute("""
        UPDATE user_profiles
        SET account_balance = COALESCE((profile->>'account_balance')::float, 0.0),
            max_position_size_pct = COALESCE((risk_profile->>'max_position_size_pct')::float, 5.0),
            max_risk_per_trade_pct = COALESCE((risk_profile->>'max_risk_per_trade_pct')::float, 1.0),
            max_daily_loss_pct = COALESCE((risk_profile->>'max_daily_loss_pct')::float, 3.0),
            min_risk_reward_ratio = COALESCE((risk_profile->>'min_risk_reward_ratio')::float, 2.0),
            default_timeframes = COALESCE(profile->'default_timeframes', '["1Min", "5Min", "15Min", "1Hour"]'::jsonb),
            experience_level = profile->>'experience_level',
            trading_style = profile->>'trading_style'
    """)

    # --- Step 3: Re-add CHECK constraints ---
    op.create_check_constraint(
        "ck_profile_balance_positive", "user_profiles", "account_balance >= 0"
    )
    op.create_check_constraint(
        "ck_profile_max_position_pct_range",
        "user_profiles",
        "max_position_size_pct > 0 AND max_position_size_pct <= 100",
    )
    op.create_check_constraint(
        "ck_profile_max_risk_pct_range",
        "user_profiles",
        "max_risk_per_trade_pct > 0 AND max_risk_per_trade_pct <= 100",
    )
    op.create_check_constraint(
        "ck_profile_max_daily_loss_range",
        "user_profiles",
        "max_daily_loss_pct > 0 AND max_daily_loss_pct <= 100",
    )
    op.create_check_constraint(
        "ck_profile_min_rr_positive", "user_profiles", "min_risk_reward_ratio > 0"
    )

    # --- Step 4: Drop JSONB columns ---
    op.drop_column("user_profiles", "profile")
    op.drop_column("user_profiles", "risk_profile")
