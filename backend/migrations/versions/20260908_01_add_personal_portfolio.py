"""add private watchlist and paper positions

Revision ID: 20260908_01
Revises: 20260905_01
"""

import sqlalchemy as sa
from alembic import op

revision = "20260908_01"
down_revision = "20260905_01"
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
    common = (
        sa.Column("symbol", sa.String(length=64), nullable=False),
        sa.Column("market", sa.String(length=32), nullable=False),
        sa.Column("instrument_type", sa.String(length=32), nullable=False),
    )
    op.create_table(
        "watchlist_items",
        sa.Column("item_id", sa.String(length=36), nullable=False),
        *common,
        sa.Column("label", sa.String(length=160), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("item_id"),
        schema=SCHEMA,
    )
    op.create_table(
        "paper_positions",
        sa.Column("position_id", sa.String(length=36), nullable=False),
        *common,
        sa.Column("quantity", sa.Numeric(28, 8), nullable=False),
        sa.Column("average_cost", sa.Numeric(24, 8), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("position_id"),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("paper_positions", schema=SCHEMA)
    op.drop_table("watchlist_items", schema=SCHEMA)
