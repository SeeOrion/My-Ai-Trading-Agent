"""add AI simulation run history

Revision ID: 20260916_01
Revises: 20260913_01
"""

import sqlalchemy as sa
from alembic import op

revision = "20260916_01"
down_revision = "20260913_01"
branch_labels = None
depends_on = None
SCHEMA = "trading_agent"


def upgrade() -> None:
    op.create_table(
        "ai_simulation_runs",
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("portfolio_id", sa.String(length=36), nullable=False),
        sa.Column("market", sa.String(length=32), nullable=False),
        sa.Column("trigger", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("position_count", sa.Integer(), nullable=False),
        sa.Column("total_equity", sa.Numeric(24, 8)),
        sa.Column("decision_reports", sa.JSON(), nullable=False),
        sa.Column("notices", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text()),
        sa.ForeignKeyConstraint(
            ["portfolio_id"],
            [f"{SCHEMA}.ai_simulation_portfolios.portfolio_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("run_id"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_ai_simulation_runs_portfolio_completed",
        "ai_simulation_runs",
        ["portfolio_id", "completed_at"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_ai_simulation_runs_portfolio_completed",
        table_name="ai_simulation_runs",
        schema=SCHEMA,
    )
    op.drop_table("ai_simulation_runs", schema=SCHEMA)
