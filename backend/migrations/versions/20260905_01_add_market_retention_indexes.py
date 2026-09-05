"""add indexes for seven-day market-data retention

Revision ID: 20260905_01
Revises: 20260904_02
Create Date: 2026-09-05
"""

from alembic import op

revision = "20260905_01"
down_revision = "20260904_02"
branch_labels = None
depends_on = None

SCHEMA = "trading_agent"


def upgrade() -> None:
    op.create_index(
        "ix_market_snapshots_observed_at",
        "market_snapshots",
        ["observed_at"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_market_scan_runs_completed_at",
        "market_scan_runs",
        ["completed_at"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_market_scan_runs_completed_at",
        table_name="market_scan_runs",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_market_snapshots_observed_at",
        table_name="market_snapshots",
        schema=SCHEMA,
    )
