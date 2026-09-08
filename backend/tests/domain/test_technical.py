from datetime import date, timedelta
from decimal import Decimal

from ai_trading_agent.domain.aggregate.market import Instrument
from ai_trading_agent.domain.aggregate.technical import (
    PriceBar,
    aggregate_bars,
    analyze_technical_study,
)
from ai_trading_agent.domain.enums.market import Market
from ai_trading_agent.domain.enums.technical import BarTimeframe, TechnicalBias


def _bars() -> tuple[PriceBar, ...]:
    instrument = Instrument("600519.SH", Market.A_SHARE)
    start = date(2026, 1, 2)
    return tuple(
        PriceBar(
            instrument=instrument,
            session_date=start + timedelta(days=index),
            open_price=Decimal("100") + index,
            high_price=Decimal("101") + index,
            low_price=Decimal("99") + index,
            close_price=Decimal("100.5") + index,
            volume=Decimal("1000") + index * Decimal("10"),
        )
        for index in range(90)
    )


def test_study_calculates_indicators_and_an_explicitly_approximate_profile() -> None:
    bars = _bars()

    study = analyze_technical_study(
        bars[0].instrument, bars, BarTimeframe.DAILY, "fixture", profile_bins=12
    )

    assert study.indicators.sma_60 is not None
    assert study.indicators.rsi_14 == Decimal("100")
    assert study.assessment.trend is TechnicalBias.BULLISH
    assert study.volume_profile.method == "bar_volume_uniform_range"
    assert "不是逐笔成交" in study.assessment.limitations[0]


def test_weekly_aggregation_preserves_open_high_low_close_and_volume() -> None:
    bars = _bars()[:10]

    weekly = aggregate_bars(bars, BarTimeframe.WEEKLY)

    assert len(weekly) == 2
    assert weekly[0].open_price == bars[0].open_price
    assert weekly[0].close_price == bars[2].close_price
    assert weekly[0].volume == sum((bar.volume for bar in bars[:3]), Decimal("0"))
