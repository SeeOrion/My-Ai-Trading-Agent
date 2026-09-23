from decimal import Decimal

from ai_trading_agent.domain.aggregate.market import Instrument
from ai_trading_agent.domain.enums.market import InstrumentType, Market
from ai_trading_agent.domain.service.simulated_execution import (
    estimate_simulated_execution,
    minimum_trade_unit,
    quantity_for_cash_budget,
)


def test_simulated_buy_uses_adverse_fill_and_cost_instead_of_free_market_price() -> None:
    estimate = estimate_simulated_execution(
        side="buy", reference_price=Decimal("10"), quantity=Decimal("100")
    )

    assert estimate.fill_price == Decimal("10.005")
    assert estimate.cash_required > Decimal("1000")
    assert estimate.estimated_cost > 0


def test_simulated_sell_uses_adverse_fill_and_net_proceeds() -> None:
    estimate = estimate_simulated_execution(
        side="sell", reference_price=Decimal("10"), quantity=Decimal("100")
    )

    assert estimate.fill_price == Decimal("9.995")
    assert estimate.cash_proceeds < Decimal("1000")


def test_cash_budget_cannot_overdraw_after_costs_and_rounds_to_a_share_lots() -> None:
    quantity = quantity_for_cash_budget(
        cash_budget=Decimal("1000"),
        reference_price=Decimal("10"),
        lot_size=Decimal("100"),
    )

    assert quantity == Decimal("0")
    assert minimum_trade_unit(
        Instrument("600519", Market.A_SHARE, InstrumentType.EQUITY)
    ) == Decimal("100")
