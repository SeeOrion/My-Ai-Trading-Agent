"""Account agent settings, generation fences and persistent evidence audits."""

import sqlalchemy as sa
from alembic import op

revision = "20261110_01"
down_revision = "20261029_01"
branch_labels = depends_on = None


def upgrade():
    schema = "trading_agent"
    op.create_table(
        "agent_accounts",
        sa.Column(
            "portfolio_id",
            sa.String(36),
            sa.ForeignKey(f"{schema}.ai_simulation_portfolios.portfolio_id"),
            primary_key=True,
        ),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("settings", sa.JSON(), nullable=False),
        schema=schema,
    )
    op.execute(
        "INSERT INTO trading_agent.agent_accounts (portfolio_id, generation, settings) SELECT portfolio_id, 1, '{}'::json FROM trading_agent.ai_simulation_portfolios"
    )
    op.create_table(
        "agent_audits",
        sa.Column("audit_id", sa.String(36), primary_key=True),
        sa.Column(
            "portfolio_id",
            sa.String(36),
            sa.ForeignKey(f"{schema}.ai_simulation_portfolios.portfolio_id"),
            nullable=False,
        ),
        sa.Column("position_id", sa.String(36)),
        sa.Column("symbol", sa.String(64), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        schema=schema,
    )
    op.create_index("ix_agent_audits_portfolio_id", "agent_audits", ["portfolio_id"], schema=schema)


def downgrade():
    op.drop_table("agent_audits", schema="trading_agent")
    op.drop_table("agent_accounts", schema="trading_agent")
