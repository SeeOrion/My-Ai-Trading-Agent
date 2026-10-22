"""Isolate ETF simulation accounts from stock accounts."""
import sqlalchemy as sa
from alembic import op

revision = "20261022_01"
down_revision = "20261019_01"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("ai_simulation_portfolios", sa.Column("account_type", sa.String(16), nullable=False, server_default="equity"), schema="trading_agent")


def downgrade():
    op.drop_column("ai_simulation_portfolios", "account_type", schema="trading_agent")
