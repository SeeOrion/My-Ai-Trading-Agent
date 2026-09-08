"""Pure, explainable technical research over provider-neutral OHLCV bars.

The volume profile deliberately distributes *bar* volume over a bar's price
range.  It is a useful approximation when tick/order-book data is unavailable,
not exchange-level position or "main-force" data.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from itertools import groupby

from ai_trading_agent.domain.aggregate.market import Instrument
from ai_trading_agent.domain.enums.technical import BarTimeframe, TechnicalBias

ZERO = Decimal("0")
ONE_HUNDRED = Decimal("100")


@dataclass(frozen=True, slots=True)
class PriceBar:
    instrument: Instrument
    session_date: date
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    close_price: Decimal
    volume: Decimal

    def __post_init__(self) -> None:
        values = (self.open_price, self.high_price, self.low_price, self.close_price, self.volume)
        if min(values) < ZERO:
            raise ValueError("bar values must not be negative")
        if self.low_price > min(self.open_price, self.close_price):
            raise ValueError("low_price must not exceed open or close")
        if self.high_price < max(self.open_price, self.close_price):
            raise ValueError("high_price must not be below open or close")


@dataclass(frozen=True, slots=True)
class IndicatorSnapshot:
    sma_5: Decimal | None
    sma_10: Decimal | None
    sma_20: Decimal | None
    sma_60: Decimal | None
    rsi_14: Decimal | None
    macd: Decimal | None
    macd_signal: Decimal | None
    macd_histogram: Decimal | None
    obv: Decimal
    atr_14: Decimal | None


@dataclass(frozen=True, slots=True)
class VolumeProfileLevel:
    price: Decimal
    volume: Decimal
    percent_of_volume: Decimal


@dataclass(frozen=True, slots=True)
class VolumeProfile:
    levels: tuple[VolumeProfileLevel, ...]
    point_of_control: Decimal
    value_area_low: Decimal
    value_area_high: Decimal
    value_area_percent: Decimal
    method: str = "bar_volume_uniform_range"


@dataclass(frozen=True, slots=True)
class TechnicalAssessment:
    trend: TechnicalBias
    momentum: TechnicalBias
    volume_pressure: TechnicalBias
    observations: tuple[str, ...]
    limitations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TechnicalStudy:
    instrument: Instrument
    timeframe: BarTimeframe
    source: str
    bars: tuple[PriceBar, ...]
    indicators: IndicatorSnapshot
    volume_profile: VolumeProfile
    assessment: TechnicalAssessment


def aggregate_bars(bars: tuple[PriceBar, ...], timeframe: BarTimeframe) -> tuple[PriceBar, ...]:
    """Aggregate daily bars into calendar weeks/months without provider logic."""
    _validate_bars(bars)
    if timeframe is BarTimeframe.DAILY:
        return bars
    if timeframe is BarTimeframe.WEEKLY:
        def grouping_key(bar: PriceBar) -> date:
            return bar.session_date - timedelta(days=bar.session_date.weekday())
    else:
        def grouping_key(bar: PriceBar) -> date:
            return bar.session_date.replace(day=1)

    result: list[PriceBar] = []
    for _, group in groupby(bars, key=grouping_key):
        grouped = tuple(group)
        first, last = grouped[0], grouped[-1]
        result.append(
            PriceBar(
                instrument=first.instrument,
                session_date=last.session_date,
                open_price=first.open_price,
                high_price=max(bar.high_price for bar in grouped),
                low_price=min(bar.low_price for bar in grouped),
                close_price=last.close_price,
                volume=sum((bar.volume for bar in grouped), ZERO),
            )
        )
    return tuple(result)


def analyze_technical_study(
    instrument: Instrument,
    raw_daily_bars: tuple[PriceBar, ...],
    timeframe: BarTimeframe,
    source: str,
    *,
    profile_bins: int = 24,
) -> TechnicalStudy:
    if not source.strip():
        raise ValueError("source must not be empty")
    bars = aggregate_bars(raw_daily_bars, timeframe)
    if len(bars) < 15:
        raise ValueError("at least 15 bars are required for technical analysis")
    if profile_bins < 4 or profile_bins > 100:
        raise ValueError("profile_bins must be between 4 and 100")
    indicators = calculate_indicators(bars)
    profile = build_volume_profile(bars, profile_bins)
    return TechnicalStudy(
        instrument=instrument,
        timeframe=timeframe,
        source=source.strip().lower(),
        bars=bars,
        indicators=indicators,
        volume_profile=profile,
        assessment=assess_technical_state(bars, indicators, profile),
    )


def calculate_indicators(bars: tuple[PriceBar, ...]) -> IndicatorSnapshot:
    _validate_bars(bars)
    closes = tuple(bar.close_price for bar in bars)
    macd, signal, histogram = _macd(closes)
    return IndicatorSnapshot(
        sma_5=_sma(closes, 5),
        sma_10=_sma(closes, 10),
        sma_20=_sma(closes, 20),
        sma_60=_sma(closes, 60),
        rsi_14=_rsi(closes, 14),
        macd=macd,
        macd_signal=signal,
        macd_histogram=histogram,
        obv=_obv(bars),
        atr_14=_atr(bars, 14),
    )


def build_volume_profile(bars: tuple[PriceBar, ...], bins: int = 24) -> VolumeProfile:
    _validate_bars(bars)
    low = min(bar.low_price for bar in bars)
    high = max(bar.high_price for bar in bars)
    total_volume = sum((bar.volume for bar in bars), ZERO)
    if total_volume <= ZERO:
        raise ValueError("positive volume is required for a volume profile")
    if low == high:
        level = VolumeProfileLevel(low, total_volume, ONE_HUNDRED)
        return VolumeProfile((level,), low, low, high, Decimal("70"))
    width = (high - low) / Decimal(bins)
    volumes: dict[int, Decimal] = defaultdict(lambda: ZERO)
    for bar in bars:
        span = (bar.high_price - bar.low_price) / width
        covered = max(
            1,
            int(span.to_integral_value(rounding=ROUND_HALF_UP)) + 1,
        )
        start = max(0, min(bins - 1, int((bar.low_price - low) / width)))
        end = min(bins - 1, start + covered - 1)
        allocation = bar.volume / Decimal(end - start + 1)
        for index in range(start, end + 1):
            volumes[index] += allocation
    levels = tuple(
        VolumeProfileLevel(
            price=(low + width * (Decimal(index) + Decimal("0.5"))).quantize(Decimal("0.0001")),
            volume=volumes[index],
            percent_of_volume=(volumes[index] / total_volume * ONE_HUNDRED).quantize(
                Decimal("0.01")
            ),
        )
        for index in range(bins)
    )
    poc_index = max(range(bins), key=lambda index: volumes[index])
    selected = {poc_index}
    selected_volume = volumes[poc_index]
    target = total_volume * Decimal("0.70")
    left, right = poc_index - 1, poc_index + 1
    while selected_volume < target and (left >= 0 or right < bins):
        left_volume = volumes[left] if left >= 0 else Decimal("-1")
        right_volume = volumes[right] if right < bins else Decimal("-1")
        if right_volume > left_volume:
            selected.add(right)
            selected_volume += right_volume
            right += 1
        else:
            selected.add(left)
            selected_volume += left_volume
            left -= 1
    return VolumeProfile(
        levels=levels,
        point_of_control=levels[poc_index].price,
        value_area_low=levels[min(selected)].price,
        value_area_high=levels[max(selected)].price,
        value_area_percent=Decimal("70"),
    )


def assess_technical_state(
    bars: tuple[PriceBar, ...], indicators: IndicatorSnapshot, profile: VolumeProfile
) -> TechnicalAssessment:
    close = bars[-1].close_price
    trend = TechnicalBias.NEUTRAL
    if indicators.sma_20 is not None and indicators.sma_60 is not None:
        if close > indicators.sma_20 > indicators.sma_60:
            trend = TechnicalBias.BULLISH
        elif close < indicators.sma_20 < indicators.sma_60:
            trend = TechnicalBias.BEARISH
    momentum = TechnicalBias.NEUTRAL
    if indicators.rsi_14 is not None:
        if indicators.rsi_14 >= Decimal("55"):
            momentum = TechnicalBias.BULLISH
        elif indicators.rsi_14 <= Decimal("45"):
            momentum = TechnicalBias.BEARISH
    recent_obv = _obv(bars[-6:])
    volume_pressure = TechnicalBias.NEUTRAL
    if recent_obv > ZERO:
        volume_pressure = TechnicalBias.BULLISH
    elif recent_obv < ZERO:
        volume_pressure = TechnicalBias.BEARISH
    observations = [
        f"收盘价 {close}，成交量峰值（POC）约 {profile.point_of_control}",
        f"70% 成交量价值区间约 {profile.value_area_low} 至 {profile.value_area_high}",
    ]
    if indicators.rsi_14 is not None:
        observations.append(f"RSI(14) 为 {indicators.rsi_14}")
    if indicators.atr_14 is not None:
        observations.append(f"ATR(14) 为 {indicators.atr_14}")
    return TechnicalAssessment(
        trend=trend,
        momentum=momentum,
        volume_pressure=volume_pressure,
        observations=tuple(observations),
        limitations=(
            "Volume Profile 基于日/周/月 K 线成交量在价格区间内均匀分配的近似估算，"
            "不是逐笔成交或持仓筹码。",
            "趋势、动量与量能压力为规则化研究信号，不代表主力意图、价格预测或交易指令。",
        ),
    )


def _validate_bars(bars: tuple[PriceBar, ...]) -> None:
    if not bars:
        raise ValueError("at least one bar is required")
    dates = tuple(bar.session_date for bar in bars)
    if dates != tuple(sorted(dates)) or len(set(dates)) != len(dates):
        raise ValueError("bars must be strictly ordered by session_date")
    instrument = bars[0].instrument
    if any(bar.instrument != instrument for bar in bars):
        raise ValueError("bars must belong to one instrument")


def _sma(values: tuple[Decimal, ...], period: int) -> Decimal | None:
    if len(values) < period:
        return None
    return (sum(values[-period:], ZERO) / Decimal(period)).quantize(Decimal("0.0001"))


def _ema_series(values: tuple[Decimal, ...], period: int) -> tuple[Decimal, ...]:
    if not values:
        return ()
    multiplier = Decimal("2") / Decimal(period + 1)
    current = values[0]
    result = [current]
    for value in values[1:]:
        current = (value - current) * multiplier + current
        result.append(current)
    return tuple(result)


def _macd(values: tuple[Decimal, ...]) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
    if len(values) < 26:
        return None, None, None
    fast, slow = _ema_series(values, 12), _ema_series(values, 26)
    line = tuple(fast_item - slow_item for fast_item, slow_item in zip(fast, slow, strict=True))
    signal = _ema_series(line, 9)[-1]
    return (
        line[-1].quantize(Decimal("0.0001")),
        signal.quantize(Decimal("0.0001")),
        (line[-1] - signal).quantize(Decimal("0.0001")),
    )


def _rsi(values: tuple[Decimal, ...], period: int) -> Decimal | None:
    if len(values) <= period:
        return None
    changes = tuple(values[index] - values[index - 1] for index in range(1, len(values)))
    gains = sum((max(change, ZERO) for change in changes[-period:]), ZERO) / Decimal(period)
    losses = sum((max(-change, ZERO) for change in changes[-period:]), ZERO) / Decimal(period)
    if losses == ZERO:
        return ONE_HUNDRED
    return (ONE_HUNDRED - ONE_HUNDRED / (Decimal("1") + gains / losses)).quantize(Decimal("0.01"))


def _obv(bars: tuple[PriceBar, ...]) -> Decimal:
    total = ZERO
    for previous, current in zip(bars, bars[1:], strict=False):
        if current.close_price > previous.close_price:
            total += current.volume
        elif current.close_price < previous.close_price:
            total -= current.volume
    return total


def _atr(bars: tuple[PriceBar, ...], period: int) -> Decimal | None:
    if len(bars) <= period:
        return None
    ranges = tuple(
        max(
            current.high_price - current.low_price,
            abs(current.high_price - previous.close_price),
            abs(current.low_price - previous.close_price),
        )
        for previous, current in zip(bars, bars[1:], strict=False)
    )
    return (sum(ranges[-period:], ZERO) / Decimal(period)).quantize(Decimal("0.0001"))
