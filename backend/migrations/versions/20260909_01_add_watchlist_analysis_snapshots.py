"""add cached selected-instrument research snapshots

Revision ID: 20260909_01
Revises: 20260908_01
"""

import sqlalchemy as sa
from alembic import op

revision = "20260909_01"
down_revision = "20260908_01"
branch_labels = None
depends_on = None
SCHEMA = "trading_agent"


def _timestamps() -> tuple[sa.Column[object], sa.Column[object]]:
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )


def upgrade() -> None:
    op.create_table(
        "watchlist_analysis_snapshots",
        sa.Column("analysis_id", sa.String(length=36), nullable=False),
        sa.Column("watchlist_item_id", sa.String(length=36), nullable=False),
        sa.Column("symbol", sa.String(length=64), nullable=False),
        sa.Column("market", sa.String(length=32), nullable=False),
        sa.Column("instrument_type", sa.String(length=32), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("ai_summary", sa.Text()),
        sa.Column("notices", sa.JSON(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["watchlist_item_id"],
            [f"{SCHEMA}.watchlist_items.item_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("analysis_id"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_watchlist_analysis_snapshots_item_observed",
        "watchlist_analysis_snapshots",
        ["watchlist_item_id", "observed_at"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_watchlist_analysis_snapshots_observed_at",
        "watchlist_analysis_snapshots",
        ["observed_at"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_watchlist_analysis_snapshots_observed_at",
        table_name="watchlist_analysis_snapshots",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_watchlist_analysis_snapshots_item_observed",
        table_name="watchlist_analysis_snapshots",
        schema=SCHEMA,
    )
    op.drop_table("watchlist_analysis_snapshots", schema=SCHEMA)
