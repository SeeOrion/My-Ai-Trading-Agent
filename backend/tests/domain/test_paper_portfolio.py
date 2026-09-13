from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from ai_trading_agent.domain.aggregate.market import Instrument, Quote
from ai_trading_agent.domain.aggregate.watchlist import (
    PaperPosition,
    summarize_paper_portfolio,
    value_paper_position,
)
from ai_trading_agent.domain.enums.market import Market
from ai_trading_agent.domain.service.position_metrics import calculate_position_metrics


def _position(symbol: str, quantity: str, cost: str) -> PaperPosition:
    return PaperPosition(
        position_id=uuid4(),
        instrument=Instrument(symbol, Market.A_SHARE),
        quantity=Decimal(quantity),
        average_cost=Decimal(cost),
    )


def _quote(position: PaperPosition, last: str, previous: str) -> Quote:
    return Quote(
        instrument=position.instrument,
        last_price=Decimal(last),
        previous_close=Decimal(previous),
        observed_at=datetime(2026, 9, 13, tzinfo=UTC),
        source="test",
    )


def test_paper_portfolio_summary_uses_cost_basis_and_preserves_currency_boundary() -> None:
    first = _position("600001.SH", "10", "10")
    second = _position("600002.SH", "5", "20")
    valuations = (
        value_paper_position(
            first,
            _quote(first, "12", "11"),
            month_reference_close=Decimal("10"),
            month_reference_date=date(2026, 8, 31),
        ),
        value_paper_position(
            second,
            _quote(second, "18", "20"),
            month_reference_close=Decimal("19"),
            month_reference_date=date(2026, 8, 31),
        ),
    )

    summary = summarize_paper_portfolio(
        valuations,
        observed_at=datetime(2026, 9, 13, tzinfo=UTC),
        total_position_count=2,
    )

    cny = summary.currencies[0]
    assert cny.currency == "CNY"
    assert cny.initial_principal == Decimal("200")
    assert cny.total_market_value == Decimal("210")
    assert cny.cumulative_pnl == Decimal("10")
    assert cny.daily_pnl == Decimal("0")
    assert cny.month_to_date_pnl == Decimal("15")
    assert cny.daily_coverage_count == 2
    assert cny.month_coverage_count == 2


def test_paper_portfolio_does_not_present_partial_monthly_total_as_complete() -> None:
    position = _position("600001.SH", "10", "10")
    valuation = value_paper_position(position, _quote(position, "12", "11"))

    summary = summarize_paper_portfolio(
        (valuation,),
        observed_at=datetime(2026, 9, 13, tzinfo=UTC),
        total_position_count=1,
    )

    assert summary.currencies[0].daily_pnl == Decimal("10")
    assert summary.currencies[0].month_to_date_pnl is None


def test_selected_stock_holding_exposes_cost_amount_and_unrealized_profit() -> None:
    """A chosen A-share holding can reuse the pure cost and P&L calculation."""
    selected_stock = _position("600519.SH", "100", "1500")

    metrics = calculate_position_metrics(
        selected_stock.quantity,
        selected_stock.average_cost,
        market_price=Decimal("1562.50"),
    )
    valuation = value_paper_position(
        selected_stock,
        _quote(selected_stock, "1562.50", "1550"),
    )

    assert selected_stock.cost_basis == Decimal("150000")
    assert metrics.cost_amount == Decimal("150000")
    assert metrics.market_value == Decimal("156250.00")
    assert metrics.unrealized_pnl == Decimal("6250.00")
    assert metrics.unrealized_pnl_percent == Decimal("4.166666666666666666666666667")
    assert valuation.unrealized_pnl == metrics.unrealized_pnl


def test_position_metrics_still_returns_cost_when_market_price_is_not_available() -> None:
    metrics = calculate_position_metrics(Decimal("200"), Decimal("12.50"))

    assert metrics.cost_amount == Decimal("2500.00")
    assert metrics.market_value is None
    assert metrics.unrealized_pnl is None
