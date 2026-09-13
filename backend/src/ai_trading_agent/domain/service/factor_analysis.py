"""Pure calculations for the ten built-in, explainable research factors."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from math import sqrt

from ai_trading_agent.domain.ability.factors import DEFAULT_FACTOR_REGISTRY, FactorMetadata
from ai_trading_agent.domain.aggregate.factor_analysis import FactorAnalysis, FactorObservation
from ai_trading_agent.domain.aggregate.market import Instrument
from ai_trading_agent.domain.aggregate.technical import PriceBar

ZERO = Decimal("0")
ONE = Decimal("1")
HUNDRED = Decimal("100")


def analyze_builtin_factors(
    instrument: Instrument,
    bars: tuple[PriceBar, ...],
    *,
    technical_source: str | None,
    pe_ttm: Decimal | None = None,
    pb_mrq: Decimal | None = None,
    roe_pct: Decimal | None = None,
    financial_source: str | None = None,
    news_sentiment: Decimal | None = None,
    news_source: str | None = None,
    observed_at: datetime | None = None,
) -> FactorAnalysis:
    """Calculate all registered default factors from facts available at this observation.

    Each unavailable input becomes a labelled unavailable observation.  This makes the
    output safe to pass to an LLM without implying that absent information is neutral.
    """
    ordered = tuple(sorted(bars, key=lambda item: item.session_date))
    metadata = {item.identifier: item for item in DEFAULT_FACTOR_REGISTRY.list()}
    observations = (
        _momentum(metadata["momentum_20d"], ordered, technical_source),
        _volatility(metadata["volatility_20d"], ordered, technical_source),
        _reversal(metadata["short_reversal_5d"], ordered, technical_source),
        _rsi(metadata["rsi_14"], ordered, technical_source),
        _moving_average_trend(metadata["moving_average_trend"], ordered, technical_source),
        _relative_volume(metadata["relative_volume_20d"], ordered, technical_source),
        _earnings_yield(metadata["earnings_yield"], pe_ttm, financial_source),
        _book_to_price(metadata["book_to_price"], pb_mrq, financial_source),
        _roe(metadata["return_on_equity"], roe_pct, financial_source),
        _sentiment(metadata["news_sentiment"], news_sentiment, news_source),
    )
    return FactorAnalysis(instrument, observed_at or datetime.now(UTC), observations)


def _unavailable(meta: FactorMetadata, reason: str) -> FactorObservation:
    return FactorObservation(
        meta.identifier, meta.name, meta.theme, None, "", "unavailable", reason, None, reason
    )


def _observation(
    meta: FactorMetadata,
    value: Decimal,
    unit: str,
    direction: str,
    interpretation: str,
    source: str | None,
) -> FactorObservation:
    return FactorObservation(
        meta.identifier, meta.name, meta.theme, value, unit, direction, interpretation, source
    )


def _require_bars(meta: FactorMetadata, bars: tuple[PriceBar, ...], required: int) -> str | None:
    if len(bars) < required:
        return f"需要至少 {required} 条日线，当前仅有 {len(bars)} 条。"
    return None


def _momentum(
    meta: FactorMetadata, bars: tuple[PriceBar, ...], source: str | None
) -> FactorObservation:
    if reason := _require_bars(meta, bars, 21):
        return _unavailable(meta, reason)
    value = _price_return(bars[-1].close_price, bars[-1 - meta.warmup_bars].close_price)
    if value is None:
        return _unavailable(meta, "基准收盘价为零，无法计算收益率。")
    direction = (
        "supportive"
        if value >= Decimal("0.03")
        else "adverse"
        if value <= Decimal("-0.03")
        else "neutral"
    )
    return _observation(meta, value * HUNDRED, "percent", direction, "20 日价格动量。", source)


def _volatility(
    meta: FactorMetadata, bars: tuple[PriceBar, ...], source: str | None
) -> FactorObservation:
    if reason := _require_bars(meta, bars, 21):
        return _unavailable(meta, reason)
    returns = _returns(bars[-21:])
    if returns is None:
        return _unavailable(meta, "收盘价包含零值，无法计算日收益率波动。")
    mean = sum(returns, ZERO) / Decimal(len(returns))
    variance = sum(((item - mean) ** 2 for item in returns), ZERO) / Decimal(len(returns))
    value = Decimal(str(sqrt(float(variance)))) * HUNDRED
    direction = (
        "supportive" if value <= Decimal("2") else "adverse" if value >= Decimal("4") else "neutral"
    )
    return _observation(
        meta, value, "percent", direction, "20 日日收益率标准差；较低代表价格波动较小。", source
    )


def _reversal(
    meta: FactorMetadata, bars: tuple[PriceBar, ...], source: str | None
) -> FactorObservation:
    if reason := _require_bars(meta, bars, 6):
        return _unavailable(meta, reason)
    recent_return = _price_return(bars[-1].close_price, bars[-1 - meta.warmup_bars].close_price)
    if recent_return is None:
        return _unavailable(meta, "基准收盘价为零，无法计算收益率。")
    value = -recent_return * HUNDRED
    direction = (
        "supportive"
        if value >= Decimal("3")
        else "adverse"
        if value <= Decimal("-3")
        else "neutral"
    )
    return _observation(
        meta,
        value,
        "percent",
        direction,
        "5 日反转值；正值代表近期回撤，须与趋势共同解读。",
        source,
    )


def _rsi(meta: FactorMetadata, bars: tuple[PriceBar, ...], source: str | None) -> FactorObservation:
    if reason := _require_bars(meta, bars, 15):
        return _unavailable(meta, reason)
    changes = [
        bars[index].close_price - bars[index - 1].close_price
        for index in range(-meta.warmup_bars, 0)
    ]
    gains = sum((max(change, ZERO) for change in changes), ZERO) / Decimal(meta.warmup_bars)
    losses = sum((max(-change, ZERO) for change in changes), ZERO) / Decimal(meta.warmup_bars)
    value = (
        HUNDRED
        if losses == ZERO and gains > ZERO
        else ZERO
        if gains == ZERO
        else HUNDRED - HUNDRED / (ONE + gains / losses)
    )
    direction = (
        "adverse"
        if value >= Decimal("70")
        else "supportive"
        if value <= Decimal("30")
        else "neutral"
    )
    return _observation(
        meta,
        value,
        "index",
        direction,
        "14 日 RSI；超买/超卖仅代表动量状态，不构成单独建议。",
        source,
    )


def _moving_average_trend(
    meta: FactorMetadata, bars: tuple[PriceBar, ...], source: str | None
) -> FactorObservation:
    if reason := _require_bars(meta, bars, 60):
        return _unavailable(meta, reason)
    slow = sum((item.close_price for item in bars[-60:]), ZERO) / Decimal("60")
    if slow == ZERO:
        return _unavailable(meta, "60 日均线为零，无法计算趋势。")
    fast = sum((item.close_price for item in bars[-20:]), ZERO) / Decimal("20")
    value = (fast / slow - ONE) * HUNDRED
    direction = "supportive" if value > ZERO else "adverse" if value < ZERO else "neutral"
    return _observation(
        meta, value, "percent", direction, "20 日均线相对 60 日均线的偏离。", source
    )


def _relative_volume(
    meta: FactorMetadata, bars: tuple[PriceBar, ...], source: str | None
) -> FactorObservation:
    if reason := _require_bars(meta, bars, 21):
        return _unavailable(meta, reason)
    baseline = sum((item.volume for item in bars[-21:-1]), ZERO) / Decimal("20")
    if baseline == ZERO:
        return _unavailable(meta, "前 20 日平均成交量为零，无法计算相对成交量。")
    value = bars[-1].volume / baseline
    direction = (
        "supportive"
        if value >= Decimal("1.2")
        else "adverse"
        if value <= Decimal("0.8")
        else "neutral"
    )
    return _observation(meta, value, "ratio", direction, "最新成交量相对前 20 日日均量。", source)


def _earnings_yield(
    meta: FactorMetadata, pe_ttm: Decimal | None, source: str | None
) -> FactorObservation:
    if pe_ttm is None:
        return _unavailable(meta, "未取得 PE TTM 估值快照。")
    if pe_ttm <= ZERO:
        return _unavailable(meta, "PE TTM 为非正值，盈利收益率不适用。")
    value = ONE / pe_ttm * HUNDRED
    direction = (
        "supportive" if value >= Decimal("5") else "adverse" if value <= Decimal("1") else "neutral"
    )
    return _observation(
        meta,
        value,
        "percent",
        direction,
        "PE TTM 的倒数，数值越高代表同口径盈利收益率越高。",
        source,
    )


def _book_to_price(
    meta: FactorMetadata, pb_mrq: Decimal | None, source: str | None
) -> FactorObservation:
    if pb_mrq is None:
        return _unavailable(meta, "未取得 PB MRQ 估值快照。")
    if pb_mrq <= ZERO:
        return _unavailable(meta, "PB MRQ 为非正值，账面市值比不适用。")
    value = ONE / pb_mrq
    direction = (
        "supportive" if value >= ONE else "adverse" if value <= Decimal("0.2") else "neutral"
    )
    return _observation(
        meta, value, "ratio", direction, "PB MRQ 的倒数；需结合资产质量判断。", source
    )


def _roe(meta: FactorMetadata, roe_pct: Decimal | None, source: str | None) -> FactorObservation:
    if roe_pct is None:
        return _unavailable(meta, "未取得已披露 ROE 财务指标。")
    direction = (
        "supportive" if roe_pct >= Decimal("15") else "adverse" if roe_pct < ZERO else "neutral"
    )
    return _observation(
        meta, roe_pct, "percent", direction, "已披露财报 ROE；报告期与公告日以数据源为准。", source
    )


def _sentiment(
    meta: FactorMetadata, score: Decimal | None, source: str | None
) -> FactorObservation:
    if score is None:
        return _unavailable(meta, "未采集到可供计算的财经资讯情绪。")
    direction = (
        "supportive"
        if score >= Decimal("0.2")
        else "adverse"
        if score <= Decimal("-0.2")
        else "neutral"
    )
    return _observation(meta, score, "score", direction, "已采集财经资讯的可解释情绪均值。", source)


def _price_return(current: Decimal, previous: Decimal) -> Decimal | None:
    return None if previous == ZERO else current / previous - ONE


def _returns(bars: tuple[PriceBar, ...]) -> list[Decimal] | None:
    values: list[Decimal] = []
    for previous, current in zip(bars, bars[1:], strict=False):
        result = _price_return(current.close_price, previous.close_price)
        if result is None:
            return None
        values.append(result)
    return values
