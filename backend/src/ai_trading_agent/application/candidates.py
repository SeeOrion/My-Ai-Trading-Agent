"""Use case for research-only, explainable daily candidate ranking."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from ai_trading_agent.application.ports import MarketCandidateProvider, MarketDataProvider
from ai_trading_agent.domain.aggregate.candidate import CandidateObservation, RankedCandidate
from ai_trading_agent.domain.aggregate.market import Instrument, Quote
from ai_trading_agent.domain.enums.candidates import CandidateRanking
from ai_trading_agent.domain.enums.market import Market


@dataclass(frozen=True, slots=True)
class RankMarketCandidates:
    market: Market
    ranking: CandidateRanking = CandidateRanking.COMPOSITE
    limit: int = 3

    def __post_init__(self) -> None:
        if not 1 <= self.limit <= 10:
            raise ValueError("candidate limit must be between 1 and 10")


@dataclass(frozen=True, slots=True)
class CandidateScreen:
    candidates: tuple[RankedCandidate, ...]
    universe_size: int


class RankMarketCandidatesHandler:
    """Scores one known universe using only fields present in every observation.

    The score is intentionally a screen: intraday movement, activity and price
    position in today's range. It must never be treated as an execution signal.
    """

    def __init__(self, provider: MarketCandidateProvider) -> None:
        self._provider = provider

    async def handle(self, query: RankMarketCandidates) -> CandidateScreen:
        observations = await self._provider.get_candidate_observations(query.market)
        if not observations:
            raise RuntimeError(f"{self._provider.name}: candidate universe is empty")
        ranked = _rank(observations, query.ranking)
        return CandidateScreen(
            candidates=tuple(ranked[: query.limit]),
            universe_size=len(observations),
        )


@dataclass(frozen=True, slots=True)
class FailoverMarketCandidateProvider:
    """Use the first source that returns a non-empty bounded candidate universe."""

    providers: tuple[MarketCandidateProvider, ...]
    name: str = "candidate_failover"

    async def get_candidate_observations(self, market: Market) -> list[CandidateObservation]:
        errors: list[str] = []
        for provider in self.providers:
            try:
                observations = await provider.get_candidate_observations(market)
            except Exception as error:
                errors.append(f"{provider.name}: {error}")
                continue
            if observations:
                return observations
            errors.append(f"{provider.name}: candidate universe is empty")
        raise RuntimeError("; ".join(errors) or "no candidate provider is configured")


@dataclass(frozen=True, slots=True)
class QuoteUniverseCandidateProvider:
    """Adapt provider-neutral quotes for the shared bounded research universe."""

    quote_provider: MarketDataProvider

    @property
    def name(self) -> str:
        return f"{self.quote_provider.name}_candidate_universe"

    async def get_candidate_observations(self, market: Market) -> list[CandidateObservation]:
        if not self.quote_provider.supports(market):
            raise RuntimeError(f"{self.quote_provider.name} does not support {market.value}")
        quotes = await self.quote_provider.get_latest_quotes(research_universe(market))
        return [_observation_from_quote(quote) for quote in quotes]


def research_universe(market: Market) -> tuple[Instrument, ...]:
    symbols = _RESEARCH_UNIVERSES.get(market, ())
    if not symbols:
        raise ValueError(f"no bounded candidate universe for market: {market.value}")
    return tuple(Instrument(symbol, market) for symbol in symbols)


def _observation_from_quote(quote: Quote) -> CandidateObservation:
    previous_close = quote.previous_close
    change_percent = (
        None
        if previous_close in {None, Decimal("0")}
        else (quote.last_price - previous_close) * Decimal("100") / previous_close
    )
    return CandidateObservation(
        instrument=quote.instrument,
        name=quote.instrument.symbol,
        last_price=quote.last_price,
        change_percent=change_percent,
        # Not every quote source exposes turnover. Volume is still a valid
        # within-source activity percentile and is never compared across sources.
        turnover=quote.volume,
        high_price=quote.high_price,
        low_price=quote.low_price,
        observed_at=quote.observed_at,
        source=quote.source,
    )


def _rank(
    observations: list[CandidateObservation], ranking: CandidateRanking
) -> list[RankedCandidate]:
    momentum = _percentile_scores(observations, lambda item: item.change_percent)
    activity = _percentile_scores(observations, lambda item: item.turnover)
    entry_balance = {id(item): _entry_balance_score(item) for item in observations}

    results: list[RankedCandidate] = []
    for item in observations:
        momentum_score = momentum[id(item)]
        activity_score = activity[id(item)]
        balance_score = entry_balance[id(item)]
        if ranking is CandidateRanking.MOMENTUM:
            score = Decimal("0.75") * momentum_score + Decimal("0.25") * activity_score
        elif ranking is CandidateRanking.BALANCED_ENTRY:
            score = (
                Decimal("0.35") * momentum_score
                + Decimal("0.15") * activity_score
                + Decimal("0.50") * balance_score
            )
        else:
            score = (
                Decimal("0.50") * momentum_score
                + Decimal("0.25") * activity_score
                + Decimal("0.25") * balance_score
            )
        results.append(
            RankedCandidate(
                observation=item,
                score=score.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP),
                reasons=_reasons(item, momentum_score, activity_score, balance_score),
            )
        )
    return sorted(
        results,
        key=lambda item: (item.score, item.observation.change_percent or Decimal("-999")),
        reverse=True,
    )


def _percentile_scores(
    observations: list[CandidateObservation],
    value_of: Callable[[CandidateObservation], Decimal | None],
) -> dict[int, Decimal]:
    values = [value_of(item) for item in observations]
    present = sorted(value for value in values if value is not None)
    if not present:
        return {id(item): Decimal("50") for item in observations}
    result: dict[int, Decimal] = {}
    denominator = max(len(present) - 1, 1)
    for item, value in zip(observations, values, strict=True):
        if value is None:
            result[id(item)] = Decimal("50")
            continue
        position = sum(candidate <= value for candidate in present) - 1
        result[id(item)] = (Decimal(position) * Decimal("100")) / Decimal(denominator)
    return result


def _entry_balance_score(item: CandidateObservation) -> Decimal:
    if (
        item.high_price is None
        or item.low_price is None
        or item.high_price <= item.low_price
    ):
        return Decimal("50")
    position = (item.last_price - item.low_price) / (item.high_price - item.low_price)
    # A mid-to-upper range price is treated as balanced; a close at the high is
    # not automatically rewarded as it can represent a stretched intraday entry.
    distance = abs(position - Decimal("0.65"))
    return max(Decimal("0"), Decimal("100") - distance * Decimal("200"))


def _reasons(
    item: CandidateObservation,
    momentum_score: Decimal,
    activity_score: Decimal,
    balance_score: Decimal,
) -> tuple[str, ...]:
    change = "数据缺失" if item.change_percent is None else f"当日变动 {item.change_percent:+.2f}%"
    return (
        change,
        f"成交活跃度位于样本池约第 {activity_score:.0f} 百分位",
        f"日内价格位置平衡度 {balance_score:.0f}/100；趋势强度 {momentum_score:.0f}/100",
    )


# All candidate adapters share this bounded liquid-stock universe. It is not an
# exchange-wide scan, so a provider outage never expands workload unexpectedly.
_RESEARCH_UNIVERSES: dict[Market, tuple[str, ...]] = {
    Market.A_SHARE: (
        "600519",
        "300750",
        "000001",
        "600036",
        "000858",
        "601318",
        "600900",
        "601888",
        "000333",
        "002594",
        "600276",
        "601012",
        "600030",
        "601166",
        "000725",
        "002475",
        "600309",
        "600809",
        "000063",
        "601398",
        "600031",
        "002371",
        "000651",
        "601668",
    ),
    Market.HONG_KONG: (
        "00700",
        "09988",
        "03690",
        "01810",
        "00005",
        "00941",
        "01299",
        "02318",
        "00939",
        "01398",
        "03988",
        "00883",
        "02628",
        "02020",
        "09618",
        "09888",
        "06618",
        "01024",
        "01093",
        "00388",
        "01177",
        "02331",
        "00175",
        "00669",
        "00857",
        "0016",
        "01928",
    ),
    Market.UNITED_STATES: (
        "AAPL",
        "MSFT",
        "NVDA",
        "AMZN",
        "GOOGL",
        "META",
        "TSLA",
        "AVGO",
        "NFLX",
        "AMD",
        "CRM",
        "ORCL",
        "JPM",
        "V",
        "MA",
        "WMT",
        "COST",
        "LLY",
        "XOM",
        "JNJ",
        "PLTR",
        "CSCO",
        "IBM",
        "ADBE",
        "QCOM",
        "INTC",
        "GE",
        "BAC",
        "HD",
        "KO",
    ),
}
