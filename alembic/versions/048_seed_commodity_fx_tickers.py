"""Seed commodity and forex tickers from TwelveData.

Inserts commonly traded commodity and forex tickers into the tickers
table with appropriate asset_type and asset_class values.
Uses ON CONFLICT DO NOTHING to avoid duplicates on re-run.

Revision ID: 048
Revises: 047
Create Date: 2026-02-22
"""

from alembic import op
import sqlalchemy as sa

revision = "048"
down_revision = "047"
branch_labels = None
depends_on = None

COMMODITIES = [
    # Precious metals - spot
    ("XAU/USD", "Gold Spot", "commodity", "commodity"),
    ("XAG/USD", "Silver Spot", "commodity", "commodity"),
    ("XPT/USD", "Platinum Spot", "commodity", "commodity"),
    ("XPD/USD", "Palladium Spot", "commodity", "commodity"),
    # Energy - spot
    ("WTI/USD", "Crude Oil WTI Spot", "commodity", "commodity"),
    ("XBR/USD", "Brent Crude Oil Spot", "commodity", "commodity"),
    ("NG/USD", "Natural Gas", "commodity", "commodity"),
    # Energy - futures
    ("CL1", "Crude Oil Futures", "commodity", "commodity"),
    ("CO1", "Brent Futures", "commodity", "commodity"),
    ("XB1", "Gasoline Futures", "commodity", "commodity"),
    ("DL1", "Ethanol Futures", "commodity", "commodity"),
    # Metals - futures
    ("HG1", "Copper Futures", "commodity", "commodity"),
    ("NI1", "Nickel Futures", "commodity", "commodity"),
    ("LMAHDS03", "Aluminum Futures", "commodity", "commodity"),
    ("UXA", "Uranium Futures", "commodity", "commodity"),
    # Agriculture
    ("C_1", "Corn Futures", "commodity", "commodity"),
    ("S_1", "Soybeans Futures", "commodity", "commodity"),
    ("W_1", "Wheat Futures", "commodity", "commodity"),
    ("KC1", "Coffee Futures", "commodity", "commodity"),
    ("CC1", "Cocoa Futures", "commodity", "commodity"),
    ("CT1", "Cotton Futures", "commodity", "commodity"),
    ("SB1", "Sugar Futures", "commodity", "commodity"),
    ("LB1", "Lumber Futures", "commodity", "commodity"),
    ("O_1", "Oat Futures", "commodity", "commodity"),
    ("RR1", "Rice Futures", "commodity", "commodity"),
    # Livestock
    ("LC1", "Live Cattle Futures", "commodity", "commodity"),
    ("LH1", "Lean Hogs Futures", "commodity", "commodity"),
    ("FC1", "Feeder Cattle Futures", "commodity", "commodity"),
]

FOREX = [
    # Majors
    ("EUR/USD", "Euro / US Dollar", "forex", "fx"),
    ("GBP/USD", "British Pound / US Dollar", "forex", "fx"),
    ("USD/JPY", "US Dollar / Japanese Yen", "forex", "fx"),
    ("USD/CHF", "US Dollar / Swiss Franc", "forex", "fx"),
    ("AUD/USD", "Australian Dollar / US Dollar", "forex", "fx"),
    ("USD/CAD", "US Dollar / Canadian Dollar", "forex", "fx"),
    ("NZD/USD", "New Zealand Dollar / US Dollar", "forex", "fx"),
    # Minors
    ("EUR/GBP", "Euro / British Pound", "forex", "fx"),
    ("EUR/JPY", "Euro / Japanese Yen", "forex", "fx"),
    ("EUR/AUD", "Euro / Australian Dollar", "forex", "fx"),
    ("EUR/CAD", "Euro / Canadian Dollar", "forex", "fx"),
    ("EUR/CHF", "Euro / Swiss Franc", "forex", "fx"),
    ("EUR/NZD", "Euro / New Zealand Dollar", "forex", "fx"),
    ("GBP/JPY", "British Pound / Japanese Yen", "forex", "fx"),
    ("GBP/AUD", "British Pound / Australian Dollar", "forex", "fx"),
    ("GBP/CAD", "British Pound / Canadian Dollar", "forex", "fx"),
    ("GBP/CHF", "British Pound / Swiss Franc", "forex", "fx"),
    ("AUD/JPY", "Australian Dollar / Japanese Yen", "forex", "fx"),
    ("AUD/NZD", "Australian Dollar / New Zealand Dollar", "forex", "fx"),
    ("AUD/CAD", "Australian Dollar / Canadian Dollar", "forex", "fx"),
    ("NZD/JPY", "New Zealand Dollar / Japanese Yen", "forex", "fx"),
    ("CAD/JPY", "Canadian Dollar / Japanese Yen", "forex", "fx"),
    ("CHF/JPY", "Swiss Franc / Japanese Yen", "forex", "fx"),
]


def upgrade() -> None:
    conn = op.get_bind()

    for symbol, name, asset_type, asset_class in COMMODITIES + FOREX:
        conn.execute(
            sa.text(
                "INSERT INTO tickers (symbol, name, exchange, asset_type, asset_class, is_active, created_at, updated_at) "
                "VALUES (:symbol, :name, 'TWELVEDATA', :asset_type, :asset_class, true, NOW(), NOW()) "
                "ON CONFLICT (symbol) DO UPDATE SET "
                "  name = EXCLUDED.name, "
                "  exchange = EXCLUDED.exchange, "
                "  asset_type = EXCLUDED.asset_type, "
                "  asset_class = EXCLUDED.asset_class, "
                "  is_active = true, "
                "  updated_at = NOW()"
            ),
            {"symbol": symbol, "name": name, "asset_type": asset_type, "asset_class": asset_class},
        )


def downgrade() -> None:
    conn = op.get_bind()
    symbols = [s for s, _, _, _ in COMMODITIES + FOREX]
    for symbol in symbols:
        conn.execute(
            sa.text("DELETE FROM tickers WHERE symbol = :symbol AND exchange = 'TWELVEDATA'"),
            {"symbol": symbol},
        )
