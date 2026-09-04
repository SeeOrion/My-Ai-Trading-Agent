"""add personal trading disciplines

Revision ID: 20260904_01
Revises: 20260902_01
Create Date: 2026-09-04
"""

import sqlalchemy as sa
from alembic import op

revision = "20260904_01"
down_revision = "20260902_01"
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
    op.create_table(
        "trading_disciplines",
        sa.Column("discipline_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("symbol", sa.String(length=64), nullable=False),
        sa.Column("market", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("definition", sa.JSON(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("discipline_id"),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("trading_disciplines", schema=SCHEMA)
