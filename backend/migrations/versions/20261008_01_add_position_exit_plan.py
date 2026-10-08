"""Persist entry and ongoing exit plans, preserving existing positions."""

import sqlalchemy as sa
from alembic import op

revision = "20261008_01"
down_revision = "20260924_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ai_simulation_positions",
        sa.Column("exit_plan", sa.JSON(), nullable=True),
        schema="trading_agent",
    )


def downgrade() -> None:
    op.drop_column("ai_simulation_positions", "exit_plan", schema="trading_agent")
