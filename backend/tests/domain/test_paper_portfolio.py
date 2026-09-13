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
