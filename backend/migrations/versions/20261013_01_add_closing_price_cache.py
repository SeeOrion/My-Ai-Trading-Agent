"""Bounded durable closing observations, separate from trading/account state."""

import sqlalchemy as sa
from alembic import op

revision = "20261013_01"
down_revision = "20261008_01"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "closing_price_cache",
        sa.Column("symbol", sa.String(64), primary_key=True),
        sa.Column("market", sa.String(32), primary_key=True),
        sa.Column("instrument_type", sa.String(32), primary_key=True),
        sa.Column("currency", sa.String(3), primary_key=True),
        sa.Column("session_date", sa.Date(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(160), nullable=False),
        sa.Column("bars", sa.JSON(), nullable=False),
        schema="trading_agent",
    )


def downgrade():
    op.drop_table("closing_price_cache", schema="trading_agent")
