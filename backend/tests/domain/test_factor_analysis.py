from datetime import date, timedelta
from decimal import Decimal

from ai_trading_agent.domain.aggregate.market import Instrument
from ai_trading_agent.domain.aggregate.technical import PriceBar
from ai_trading_agent.domain.enums.market import Market
from ai_trading_agent.domain.service.factor_analysis import analyze_builtin_factors


def _bars(count: int = 90) -> tuple[PriceBar, ...]:
    instrument = Instrument("600519.SH", Market.A_SHARE)
    start = date(2026, 1, 2)
    return tuple(
        PriceBar(
            instrument=instrument,
            session_date=start + timedelta(days=index),
            open_price=Decimal("100") + Decimal(index),
            high_price=Decimal("101") + Decimal(index),
            low_price=Decimal("99") + Decimal(index),
            close_price=Decimal("100") + Decimal(index),
            volume=Decimal("1000") + Decimal(index) * Decimal("10"),
        )
        for index in range(count)
    )


def test_builtin_factor_analysis_calculates_all_ten_with_explicit_sources() -> None:
    analysis = analyze_builtin_factors(
        _bars()[0].instrument,
        _bars(),
        technical_source="fixture_prices",
        pe_ttm=Decimal("20"),
        pb_mrq=Decimal("2"),
        roe_pct=Decimal("16"),
        financial_source="fixture_financials",
        news_sentiment=Decimal("0.5"),
        news_source="fixture_news",
    )

    assert len(analysis.observations) == 10
    assert analysis.available_count == 10
    assert next(
        item for item in analysis.observations if item.identifier == "earnings_yield"
    ).value == Decimal("5.00")
    assert (
        next(
            item for item in analysis.observations if item.identifier == "moving_average_trend"
        ).source
        == "fixture_prices"
    )


def test_builtin_factor_analysis_preserves_missing_inputs_as_unavailable() -> None:
    analysis = analyze_builtin_factors(
        _bars(1)[0].instrument,
        _bars(1),
        technical_source="fixture_prices",
    )

    assert analysis.available_count == 0
    assert all(item.direction == "unavailable" for item in analysis.observations)
    assert all(item.unavailable_reason for item in analysis.observations)
