from collections.abc import Iterable
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ai_trading_agent.application.a_share_quote_failover import AShareQuoteFailover
from ai_trading_agent.domain.aggregate.market import Instrument, Quote
from ai_trading_agent.domain.enums.market import Market


class FixtureQuoteProvider:
    def __init__(
        self,
        name: str,
        quote: Quote | None = None,
        error: Exception | None = None,
    ) -> None:
        self.name = name
        self._quote = quote
        self._error = error
        self.calls = 0

    def supports(self, market: Market) -> bool:
        return market is Market.A_SHARE

    async def get_latest_quotes(self, instruments: Iterable[Instrument]) -> list[Quote]:
        self.calls += 1
        if self._error:
            raise self._error
        assert self._quote is not None
        return [self._quote]


@pytest.mark.asyncio
async def test_a_share_failover_uses_tushare_after_futu_failure_and_cools_down() -> None:
    instrument = Instrument("600519.SH", Market.A_SHARE)
    quote = Quote(instrument, Decimal("1420"), datetime(2026, 9, 3, tzinfo=UTC), "tushare")
    futu = FixtureQuoteProvider("futu", error=RuntimeError("no A-share quote permission"))
    tushare = FixtureQuoteProvider("tushare", quote=quote)
    now = [100.0]
    service = AShareQuoteFailover(
        futu,
        tushare,
        primary_timeout_seconds=1,
        cooldown_seconds=60,
        clock=lambda: now[0],
    )

    assert await service.get_latest_quote(instrument) == quote
    assert await service.get_latest_quote(instrument) == quote

    assert futu.calls == 1
    assert tushare.calls == 2

    now[0] = 161.0
    assert await service.get_latest_quote(instrument) == quote
    assert futu.calls == 2


@pytest.mark.asyncio
async def test_a_share_failover_keeps_futu_when_it_returns_a_quote() -> None:
    instrument = Instrument("600519.SH", Market.A_SHARE)
    quote = Quote(instrument, Decimal("1421"), datetime(2026, 9, 3, tzinfo=UTC), "futu")
    futu = FixtureQuoteProvider("futu", quote=quote)
    tushare = FixtureQuoteProvider("tushare", error=AssertionError("must not be called"))
    service = AShareQuoteFailover(futu, tushare)

    assert await service.get_latest_quote(instrument) == quote
    assert futu.calls == 1
    assert tushare.calls == 0
