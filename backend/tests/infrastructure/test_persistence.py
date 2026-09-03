import pytest

from ai_trading_agent.infrastructure.repo.database import create_database_engine
from ai_trading_agent.infrastructure.repo.models import SCHEMA, Base


def test_private_schema_contains_auditable_product_records() -> None:
    tables = set(Base.metadata.tables)

    assert f"{SCHEMA}.factor_definitions" in tables
    assert f"{SCHEMA}.documents" in tables
    assert f"{SCHEMA}.trade_journal_records" in tables


def test_database_engine_requires_async_postgresql_url() -> None:
    with pytest.raises(ValueError, match="postgresql\\+asyncpg"):
        create_database_engine("sqlite:///not-for-production.db")
