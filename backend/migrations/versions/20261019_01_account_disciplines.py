"""Bind disciplines to accounts, preserving existing enabled rules at migration."""

import sqlalchemy as sa
from alembic import op

revision = "20261019_01"
down_revision = "20261013_01"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "ai_simulation_portfolios",
        sa.Column(
            "discipline_ids", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")
        ),
        schema="trading_agent",
    )
    op.execute("""UPDATE trading_agent.ai_simulation_portfolios p
        SET discipline_ids = COALESCE((SELECT json_agg(d.discipline_id ORDER BY d.discipline_id)
        FROM trading_agent.trading_disciplines d WHERE d.market = p.market AND d.status = 'active'),
        '[]'::json)""")


def downgrade():
    op.drop_column("ai_simulation_portfolios", "discipline_ids", schema="trading_agent")
