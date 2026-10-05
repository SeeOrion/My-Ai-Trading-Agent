from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from ai_trading_agent.domain.aggregate.ai_simulation import AiSimulationPortfolio
from ai_trading_agent.domain.enums.market import Market
from ai_trading_agent.interfaces.facade import ai_simulation


class ActivePortfolioRepository:
    async def list_active(self) -> list[AiSimulationPortfolio]:
        return [
            AiSimulationPortfolio(
                portfolio_id=uuid4(),
                market=Market.A_SHARE.value,
                currency="CNY",
                initial_capital=Decimal("100000"),
                cash_balance=Decimal("100000"),
                max_positions=3,
            ),
            AiSimulationPortfolio(
                portfolio_id=uuid4(),
                market=Market.HONG_KONG.value,
                currency="HKD",
                initial_capital=Decimal("100000"),
                cash_balance=Decimal("100000"),
                max_positions=3,
            ),
        ]


class OctoberFifthCalendar:
    def is_trading_day(self, market: Market, observed_at: datetime) -> bool:
        return market is Market.HONG_KONG

    def is_open(self, market: Market, observed_at: datetime) -> bool:
        return market is Market.HONG_KONG


@pytest.mark.asyncio
async def test_scheduled_simulation_skips_only_the_closed_exchange(monkeypatch) -> None:
    requested_markets: list[Market] = []

    async def record_run(app, request):  # type: ignore[no-untyped-def]
        requested_markets.append(request.market)

    monkeypatch.setattr(
        ai_simulation,
        "ai_simulation_repository",
        lambda app: ActivePortfolioRepository(),
    )
    monkeypatch.setattr(ai_simulation, "run_ai_simulation", record_run)

    await ai_simulation.run_scheduled_ai_simulations(
        object(),  # type: ignore[arg-type]
        observed_at=datetime(2026, 10, 5, 1, 30, tzinfo=UTC),
        trading_calendar=OctoberFifthCalendar(),
    )

    assert requested_markets == [Market.HONG_KONG]
