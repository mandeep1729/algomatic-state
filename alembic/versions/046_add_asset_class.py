"""Add asset_class column to tickers table.

Adds a new column to classify tickers by asset class (stock, commodity,
fx, etf, option, crypto). Existing rows default to 'stock'. A data
migration maps existing asset_type values to the appropriate asset_class.

Revision ID: 046
Revises: 045
Create Date: 2026-02-22
"""

from alembic import op
import sqlalchemy as sa

revision = "046"
down_revision = "045"
branch_labels = None
depends_on = None


# Map existing asset_type values to the new asset_class column.
ASSET_TYPE_TO_CLASS = {
    "stock": "stock",
    "etf": "etf",
    "crypto": "crypto",
    "option": "option",
    "forex": "fx",
    "fx": "fx",
    "commodity": "commodity",
}


def upgrade() -> None:
    op.add_column(
        "tickers",
        sa.Column(
            "asset_class",
            sa.String(length=20),
            nullable=False,
            server_default="stock",
        ),
    )

    # Data migration: set asset_class based on existing asset_type.
    conn = op.get_bind()
    for asset_type, asset_class in ASSET_TYPE_TO_CLASS.items():
        conn.execute(
            sa.text(
                "UPDATE tickers SET asset_class = :asset_class "
                "WHERE LOWER(asset_type) = :asset_type"
            ),
            {"asset_class": asset_class, "asset_type": asset_type.lower()},
        )


def downgrade() -> None:
    op.drop_column("tickers", "asset_class")
