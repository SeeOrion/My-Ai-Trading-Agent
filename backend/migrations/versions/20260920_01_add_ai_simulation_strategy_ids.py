"""support multiple selected strategies for AI simulation portfolios

Revision ID: 20260920_01
Revises: 20260916_01
"""

import sqlalchemy as sa
from alembic import op

revision = "20260920_01"
down_revision = "20260916_01"
branch_labels = None
depends_on = None
SCHEMA = "trading_agent"


def upgrade() -> None:
    op.add_column(
        "ai_simulation_portfolios",
        sa.Column("strategy_ids", sa.JSON(), nullable=True),
        schema=SCHEMA,
    )
    op.execute(
        sa.text(
            f"""
            UPDATE {SCHEMA}.ai_simulation_portfolios
            SET strategy_ids = CASE
                WHEN strategy_id IS NULL THEN '[]'::json
                ELSE json_build_array(strategy_id)
            END
            """
        )
    )
    op.alter_column(
        "ai_simulation_portfolios",
        "strategy_ids",
        nullable=False,
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_column("ai_simulation_portfolios", "strategy_ids", schema=SCHEMA)
