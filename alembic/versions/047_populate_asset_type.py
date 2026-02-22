"""Populate asset_type column with accurate classifications.

Reclassifies tickers that are currently all 'stock' or 'etf' into more
granular types: warrant, preferred, unit, right. Uses name pattern matching.

Revision ID: 047
Revises: 046
Create Date: 2026-02-22
"""

from alembic import op
import sqlalchemy as sa

revision = "047"
down_revision = "046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # Reclassify warrants (must come before units since some units contain "warrant" in name).
    conn.execute(sa.text(
        "UPDATE tickers SET asset_type = 'warrant' "
        "WHERE asset_type = 'stock' AND name ILIKE '%warrant%'"
    ))

    # Reclassify preferred stock / depositary shares.
    conn.execute(sa.text(
        "UPDATE tickers SET asset_type = 'preferred' "
        "WHERE asset_type = 'stock' "
        "AND (name ILIKE '%preferred%' OR name ILIKE '%depositary shares%')"
    ))

    # Reclassify units.
    conn.execute(sa.text(
        "UPDATE tickers SET asset_type = 'unit' "
        "WHERE asset_type = 'stock' "
        "AND (name ILIKE '% units%' OR name ILIKE '% unit %')"
    ))

    # Reclassify rights.
    conn.execute(sa.text(
        "UPDATE tickers SET asset_type = 'right' "
        "WHERE asset_type = 'stock' "
        "AND name ILIKE '%right%' "
        "AND name NOT ILIKE '%rights reserved%'"
    ))


def downgrade() -> None:
    conn = op.get_bind()
    # Revert all reclassified types back to 'stock'.
    conn.execute(sa.text(
        "UPDATE tickers SET asset_type = 'stock' "
        "WHERE asset_type IN ('warrant', 'preferred', 'unit', 'right')"
    ))
