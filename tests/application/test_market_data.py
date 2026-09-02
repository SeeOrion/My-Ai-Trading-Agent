from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from ai_trading_agent.application.market_data import (
    GetLatestQuote,
    GetLatestQuoteHandler,
    MarketDataUnavailableError,
)
from ai_trading_agent.domain.market import Instrument, Market, Quote
from ai_trading_agent.infrastructure.market_data.static import StaticMarketDataProvider


@pytest.mark.asyncio
async def test_handler_returns_fresh_quote() -> None:
    instrument = Instrument("AAPL", Market.UNITED_STATES)
    now = datetime(2026, 9, 2, 12, 0, tzinfo=UTC)
    quote = Quote(instrument, Decimal("200"), now - timedelta(minutes=2), "fixture")
    handler = GetLatestQuoteHandler([StaticMarketDataProvider([quote])])

    result = await handler.handle(GetLatestQuote(instrument), now=now)

    assert result == quote


@pytest.mark.asyncio
async def test_handler_fails_when_only_quote_is_stale() -> None:
    instrument = Instrument("AAPL", Market.UNITED_STATES)
    now = datetime(2026, 9, 2, 12, 0, tzinfo=UTC)
    quote = Quote(instrument, Decimal("200"), now - timedelta(minutes=16), "fixture")
    handler = GetLatestQuoteHandler([StaticMarketDataProvider([quote])])

    with pytest.raises(MarketDataUnavailableError, match="stale quote"):
        await handler.handle(GetLatestQuote(instrument), now=now)
