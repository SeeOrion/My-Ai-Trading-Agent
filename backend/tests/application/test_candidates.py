from collections.abc import Iterable
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ai_trading_agent.application.candidates import (
    FailoverMarketCandidateProvider,
    QuoteUniverseCandidateProvider,
    RankMarketCandidates,
    RankMarketCandidatesHandler,
    research_universe,
)
from ai_trading_agent.domain.aggregate.candidate import CandidateObservation
from ai_trading_agent.domain.aggregate.market import Instrument, Quote
from ai_trading_agent.domain.enums.candidates import CandidateRanking
from ai_trading_agent.domain.enums.market import Market


class CandidateProvider:
    name = "test_provider"

    async def get_candidate_observations(self, market: Market) -> list[CandidateObservation]:
        return [
            _observation("AAA", market, change="1", turnover="100", last="10", high="11", low="9"),
            _observation(
                "BBB", market, change="4", turnover="300", last="10.3", high="11", low="9"
            ),
            _observation("CCC", market, change="2", turnover="200", last="9.2", high="11", low="9"),
            _observation("DDD", market, change="-1", turnover="80", last="10", high="11", low="9"),
        ]


class FailedCandidateProvider:
    name = "failed"

    async def get_candidate_observations(self, market: Market) -> list[CandidateObservation]:
        raise OSError("temporary provider failure")


class QuoteProvider:
    name = "quote_source"

    def supports(self, market: Market) -> bool:
        return market is Market.A_SHARE

    async def get_latest_quotes(self, instruments: Iterable[Instrument]) -> list[Quote]:
        return [
            Quote(
                instrument=instrument,
                last_price=Decimal("11"),
                observed_at=datetime(2026, 9, 24, tzinfo=UTC),
                source=self.name,
                high_price=Decimal("12"),
                low_price=Decimal("9"),
                previous_close=Decimal("10"),
                volume=Decimal("1000"),
            )
            for instrument in instruments
        ]


def _observation(
    symbol: str,
    market: Market,
    *,
    change: str,
    turnover: str,
    last: str,
    high: str,
    low: str,
) -> CandidateObservation:
    return CandidateObservation(
        instrument=Instrument(symbol, market),
        name=symbol,
        last_price=Decimal(last),
        change_percent=Decimal(change),
        turnover=Decimal(turnover),
        high_price=Decimal(high),
        low_price=Decimal(low),
        observed_at=datetime(2026, 9, 4, tzinfo=UTC),
        source="test_provider",
    )


@pytest.mark.asyncio
async def test_candidate_screen_returns_three_explainable_results() -> None:
    screen = await RankMarketCandidatesHandler(CandidateProvider()).handle(
        RankMarketCandidates(market=Market.UNITED_STATES, ranking=CandidateRanking.COMPOSITE)
    )

    assert screen.universe_size == 4
    assert len(screen.candidates) == 3
    assert screen.candidates[0].observation.instrument.symbol == "BBB"
    assert screen.candidates[0].score <= Decimal("100")
    assert len(screen.candidates[0].reasons) == 3


@pytest.mark.asyncio
async def test_balanced_entry_lens_is_separate_from_momentum_lens() -> None:
    handler = RankMarketCandidatesHandler(CandidateProvider())

    momentum = await handler.handle(
        RankMarketCandidates(
            market=Market.A_SHARE,
            ranking=CandidateRanking.MOMENTUM,
            limit=4,
        )
    )
    balanced = await handler.handle(
        RankMarketCandidates(
            market=Market.A_SHARE,
            ranking=CandidateRanking.BALANCED_ENTRY,
            limit=4,
        )
    )

    momentum_scores = {
        item.observation.instrument.symbol: item.score for item in momentum.candidates
    }
    balanced_scores = {
        item.observation.instrument.symbol: item.score for item in balanced.candidates
    }
    assert momentum_scores["DDD"] != balanced_scores["DDD"]


@pytest.mark.asyncio
async def test_candidate_failover_uses_next_provider_after_primary_failure() -> None:
    provider = FailoverMarketCandidateProvider(
        (FailedCandidateProvider(), CandidateProvider())
    )

    observations = await provider.get_candidate_observations(Market.A_SHARE)

    assert len(observations) == 4
    assert observations[0].source == "test_provider"


@pytest.mark.asyncio
async def test_quote_provider_adapts_the_shared_bounded_universe() -> None:
    provider = QuoteUniverseCandidateProvider(QuoteProvider())

    observations = await provider.get_candidate_observations(Market.A_SHARE)

    assert len(observations) == len(research_universe(Market.A_SHARE))
    assert observations[0].instrument.symbol.endswith((".SH", ".SZ"))
    assert observations[0].change_percent == Decimal("10")
    assert observations[0].turnover == Decimal("1000")
    assert observations[0].source == "quote_source"
