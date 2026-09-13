"""add auditable AI paper-trading portfolios

Revision ID: 20260913_01
Revises: 20260909_01
"""

import sqlalchemy as sa
from alembic import op

revision = "20260913_01"
down_revision = "20260909_01"
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
        "ai_simulation_portfolios",
        sa.Column("portfolio_id", sa.String(length=36), nullable=False),
        sa.Column("market", sa.String(length=32), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("initial_capital", sa.Numeric(24, 8), nullable=False),
        sa.Column("cash_balance", sa.Numeric(24, 8), nullable=False),
        sa.Column("max_positions", sa.Integer(), nullable=False),
        sa.Column("strategy_id", sa.String(length=36)),
        sa.Column("status", sa.String(length=16), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["strategy_id"], [f"{SCHEMA}.strategy_profiles.strategy_id"]),
        sa.PrimaryKeyConstraint("portfolio_id"),
        schema=SCHEMA,
    )
    op.create_table(
        "ai_simulation_positions",
        sa.Column("position_id", sa.String(length=36), nullable=False),
        sa.Column("portfolio_id", sa.String(length=36), nullable=False),
        sa.Column("symbol", sa.String(length=64), nullable=False),
        sa.Column("market", sa.String(length=32), nullable=False),
        sa.Column("instrument_type", sa.String(length=32), nullable=False),
        sa.Column("quantity", sa.Numeric(28, 8), nullable=False),
        sa.Column("average_cost", sa.Numeric(24, 8), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("candidate_score", sa.Numeric(8, 2), nullable=False),
        sa.Column("factor_context", sa.JSON(), nullable=False),
        sa.Column("rationale", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["portfolio_id"], [f"{SCHEMA}.ai_simulation_portfolios.portfolio_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("position_id"),
        schema=SCHEMA,
    )
    op.create_index("ix_ai_simulation_positions_portfolio_status", "ai_simulation_positions", ["portfolio_id", "status"], schema=SCHEMA)
    op.create_table(
        "ai_simulation_trades",
        sa.Column("trade_id", sa.String(length=36), nullable=False),
        sa.Column("portfolio_id", sa.String(length=36), nullable=False),
        sa.Column("position_id", sa.String(length=36)),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("quantity", sa.Numeric(28, 8), nullable=False),
        sa.Column("price", sa.Numeric(24, 8), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rationale", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["portfolio_id"], [f"{SCHEMA}.ai_simulation_portfolios.portfolio_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["position_id"], [f"{SCHEMA}.ai_simulation_positions.position_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("trade_id"),
        schema=SCHEMA,
    )
    op.create_index("ix_ai_simulation_trades_portfolio_executed", "ai_simulation_trades", ["portfolio_id", "executed_at"], schema=SCHEMA)


def downgrade() -> None:
    op.drop_index("ix_ai_simulation_trades_portfolio_executed", table_name="ai_simulation_trades", schema=SCHEMA)
    op.drop_table("ai_simulation_trades", schema=SCHEMA)
    op.drop_index("ix_ai_simulation_positions_portfolio_status", table_name="ai_simulation_positions", schema=SCHEMA)
    op.drop_table("ai_simulation_positions", schema=SCHEMA)
    op.drop_table("ai_simulation_portfolios", schema=SCHEMA)
