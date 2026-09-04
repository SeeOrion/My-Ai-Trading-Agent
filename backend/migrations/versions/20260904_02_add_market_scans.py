"""add market scans and normalized snapshots

Revision ID: 20260904_02
Revises: 20260904_01
Create Date: 2026-09-04
"""

import sqlalchemy as sa
from alembic import op

revision = "20260904_02"
down_revision = "20260904_01"
branch_labels = None
depends_on = None

SCHEMA = "trading_agent"


def upgrade() -> None:
    op.create_table(
        "market_scan_runs",
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("market", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("universe_size", sa.Integer(), nullable=False),
        sa.Column("snapshot_count", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("run_id"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_market_scan_runs_market_started",
        "market_scan_runs",
        ["market", "started_at"],
        schema=SCHEMA,
    )
    op.create_table(
        "market_snapshots",
        sa.Column("snapshot_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("market", sa.String(length=32), nullable=False),
        sa.Column("symbol", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("last_price", sa.Numeric(24, 8), nullable=False),
        sa.Column("previous_close", sa.Numeric(24, 8)),
        sa.Column("open_price", sa.Numeric(24, 8)),
        sa.Column("high_price", sa.Numeric(24, 8)),
        sa.Column("low_price", sa.Numeric(24, 8)),
        sa.Column("volume", sa.Numeric(28, 4)),
        sa.Column("turnover", sa.Numeric(28, 4)),
        sa.Column("change_percent", sa.Numeric(16, 8)),
        sa.Column("price_to_earnings", sa.Numeric(20, 8)),
        sa.Column("price_to_book", sa.Numeric(20, 8)),
        sa.ForeignKeyConstraint(["run_id"], [f"{SCHEMA}.market_scan_runs.run_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("snapshot_id"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_market_snapshots_run_symbol",
        "market_snapshots",
        ["run_id", "symbol"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index("ix_market_snapshots_run_symbol", table_name="market_snapshots", schema=SCHEMA)
    op.drop_table("market_snapshots", schema=SCHEMA)
    op.drop_index("ix_market_scan_runs_market_started", table_name="market_scan_runs", schema=SCHEMA)
    op.drop_table("market_scan_runs", schema=SCHEMA)
