from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from ai_trading_agent.domain.aggregate.ai_simulation import (
    AiSimulationPortfolio,
    AiSimulationPosition,
)
from ai_trading_agent.domain.aggregate.market import Instrument, Quote
from ai_trading_agent.domain.enums.market import Market
from ai_trading_agent.domain.service.simulation_exit import SimulationExitDecision
from ai_trading_agent.interfaces.facade.ai_simulation import _execute_position_sale


class RecordingSimulationRepository:
    def __init__(self) -> None:
        self.position = None
        self.trade = None
        self.portfolio = None

    async def save_position(self, position):  # type: ignore[no-untyped-def]
        self.position = position
        return position

    async def save_trade(self, trade):  # type: ignore[no-untyped-def]
        self.trade = trade
        return trade

    async def save_portfolio(self, portfolio):  # type: ignore[no-untyped-def]
        self.portfolio = portfolio
        return portfolio


@pytest.mark.asyncio
async def test_partial_profit_sale_updates_cash_and_keeps_remainder_open() -> None:
    repository = RecordingSimulationRepository()
    portfolio = AiSimulationPortfolio(
        portfolio_id=uuid4(),
        market="a_share",
        currency="CNY",
        initial_capital=Decimal("100000"),
        cash_balance=Decimal("1000"),
        max_positions=3,
    )
    instrument = Instrument("600519.SH", Market.A_SHARE)
    position = AiSimulationPosition(
        position_id=uuid4(),
        portfolio_id=portfolio.portfolio_id,
        instrument=instrument,
        quantity=Decimal("1000"),
        average_cost=Decimal("100"),
        opened_at=datetime(2026, 9, 1, tzinfo=UTC),
        candidate_score=Decimal("82"),
        factor_context=("momentum_20d",),
        rationale=("入场证据。",),
        highest_price=Decimal("120"),
    )
    quote = Quote(
        instrument=instrument,
        last_price=Decimal("120"),
        observed_at=datetime(2026, 9, 24, tzinfo=UTC),
        source="test",
    )
    decision = SimulationExitDecision(
        action="partial_exit",
        quantity=Decimal("500"),
        reason_code="first_profit_target",
        rationale=("达到首次盈利目标。",),
        highest_price=Decimal("120"),
        profit_take_stage=1,
        trailing_stop_price=Decimal("114"),
    )

    updated_portfolio, updated_position, _ = await _execute_position_sale(
        repository, portfolio, position, quote, decision  # type: ignore[arg-type]
    )

    assert updated_position is not None
    assert updated_position.quantity == Decimal("500")
    assert updated_position.status == "open"
    assert updated_position.profit_take_stage == 1
    assert updated_position.trailing_stop_price == Decimal("114")
    assert repository.trade.side == "sell"
    assert repository.trade.quantity == Decimal("500")
    assert updated_portfolio.cash_balance > portfolio.cash_balance
