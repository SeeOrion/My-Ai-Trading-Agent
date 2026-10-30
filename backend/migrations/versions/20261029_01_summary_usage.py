"""Persist semantic summary baselines and private LLM usage counters."""

import sqlalchemy as sa
from alembic import op

revision = "20261029_01"
down_revision = "20261022_01"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "watchlist_analysis_snapshots",
        sa.Column("summary_state", sa.JSON()),
        schema="trading_agent",
    )
    op.add_column(
        "watchlist_analysis_snapshots",
        sa.Column("summary_generated_at", sa.DateTime(timezone=True)),
        schema="trading_agent",
    )
    op.create_table(
        "llm_usage",
        sa.Column("event_id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("feature", sa.String(64), nullable=False),
        sa.Column("model", sa.String(160), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("reason", sa.String(160), nullable=False),
        *(
            sa.Column(name, sa.Integer())
            for name in (
                "input_tokens",
                "output_tokens",
                "total_tokens",
                "cached_tokens",
                "reasoning_tokens",
            )
        ),
        schema="trading_agent",
    )
    op.create_index("ix_llm_usage_created_at", "llm_usage", ["created_at"], schema="trading_agent")


def downgrade():
    op.drop_table("llm_usage", schema="trading_agent")
    op.drop_column("watchlist_analysis_snapshots", "summary_generated_at", schema="trading_agent")
    op.drop_column("watchlist_analysis_snapshots", "summary_state", schema="trading_agent")
