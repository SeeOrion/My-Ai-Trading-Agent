"""add persistent AI simulation exit state

Revision ID: 20260924_01
Revises: 20260920_01
"""

import sqlalchemy as sa
from alembic import op

revision = "20260924_01"
down_revision = "20260920_01"
branch_labels = None
depends_on = None
SCHEMA = "trading_agent"


def upgrade() -> None:
    op.add_column(
        "ai_simulation_positions",
        sa.Column("highest_price", sa.Numeric(24, 8), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "ai_simulation_positions",
        sa.Column(
            "profit_take_stage",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        schema=SCHEMA,
    )
    op.add_column(
        "ai_simulation_positions",
        sa.Column("trailing_stop_price", sa.Numeric(24, 8), nullable=True),
        schema=SCHEMA,
    )
    op.execute(
        sa.text(
            f"UPDATE {SCHEMA}.ai_simulation_positions "
            "SET highest_price = average_cost WHERE highest_price IS NULL"
        )
    )
    op.alter_column(
        "ai_simulation_positions",
        "highest_price",
        existing_type=sa.Numeric(24, 8),
        nullable=False,
        schema=SCHEMA,
    )
    op.alter_column(
        "ai_simulation_positions",
        "profit_take_stage",
        server_default=None,
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_column("ai_simulation_positions", "trailing_stop_price", schema=SCHEMA)
    op.drop_column("ai_simulation_positions", "profit_take_stage", schema=SCHEMA)
    op.drop_column("ai_simulation_positions", "highest_price", schema=SCHEMA)
