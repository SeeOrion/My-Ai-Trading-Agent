"""initial private trading-agent schema

Revision ID: 20260902_01
Revises:
Create Date: 2026-09-02
"""

import sqlalchemy as sa
from alembic import op

revision = "20260902_01"
down_revision = None
branch_labels = None
depends_on = None

SCHEMA = "trading_agent"


def _timestamps() -> tuple[sa.Column[object], sa.Column[object]]:
    return (
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")
    op.create_table(
        "factor_definitions",
        sa.Column("identifier", sa.String(length=64), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("theme", sa.String(length=64), nullable=False),
        sa.Column("formula", sa.Text(), nullable=False),
        sa.Column("columns_required", sa.JSON(), nullable=False),
        sa.Column("warmup_bars", sa.Integer(), nullable=False),
        sa.Column("horizon_days", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("identifier", "version"),
        schema=SCHEMA,
    )
    op.create_table(
        "strategy_profiles",
        sa.Column("strategy_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("definition", sa.JSON(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("strategy_id"),
        schema=SCHEMA,
    )
    op.create_table(
        "documents",
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("media_type", sa.String(length=128), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("extraction_status", sa.String(length=32), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("document_id"),
        sa.UniqueConstraint("sha256"),
        sa.UniqueConstraint("storage_key"),
        schema=SCHEMA,
    )
    op.create_table(
        "trade_journal_records",
        sa.Column("record_id", sa.String(length=36), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("traded_on", sa.Date(), nullable=False),
        sa.Column("market", sa.String(length=32), nullable=False),
        sa.Column("symbol", sa.String(length=64), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("quantity", sa.String(length=64), nullable=False),
        sa.Column("price", sa.String(length=64), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("fees", sa.String(length=64), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("record_id"),
        schema=SCHEMA,
    )
    op.create_table(
        "strategy_runs",
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("strategy_id", sa.String(length=36), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["strategy_id"], [f"{SCHEMA}.strategy_profiles.strategy_id"]),
        sa.PrimaryKeyConstraint("run_id"),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("strategy_runs", schema=SCHEMA)
    op.drop_table("trade_journal_records", schema=SCHEMA)
    op.drop_table("documents", schema=SCHEMA)
    op.drop_table("strategy_profiles", schema=SCHEMA)
    op.drop_table("factor_definitions", schema=SCHEMA)
    op.execute(f"DROP SCHEMA IF EXISTS {SCHEMA}")
