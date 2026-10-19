from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from ai_trading_agent.domain.ability.closing_prices import ClosingPrices
from ai_trading_agent.domain.aggregate.market import Instrument, Quote
from ai_trading_agent.domain.aggregate.technical import PriceBar
from ai_trading_agent.domain.aggregate.watchlist import PaperPosition, value_paper_position
from ai_trading_agent.domain.enums.market import Market
from ai_trading_agent.domain.service.monthly_basis import monthly_basis
from ai_trading_agent.interfaces.facade import closing_valuation as module

INSTRUMENT = Instrument("600519.SH", Market.A_SHARE)
NOW = datetime(2026, 10, 19, 8, tzinfo=UTC)


@pytest.mark.parametrize(
    "opened,expected",
    [(datetime(2026, 10, 12, tzinfo=UTC), "200"), (datetime(2026, 9, 12, tzinfo=UTC), "100")],
)
def test_monthly_basis_excludes_moves_before_purchase(opened, expected):
    position = PaperPosition(uuid4(), INSTRUMENT, Decimal(100), Decimal(10), opened_at=opened)
    quote = Quote(INSTRUMENT, Decimal(12), NOW, "test")
    price, day, _ = monthly_basis(position, quote, (date(2026, 9, 30), Decimal(11)))
    result = value_paper_position(
        position, quote, month_reference_close=price, month_reference_date=day
    )
    assert result.month_to_date_pnl == Decimal(expected)


def test_missing_basis_is_explicit_cost_estimate():
    position = PaperPosition(uuid4(), INSTRUMENT, Decimal(100), Decimal(10))
    price, day, notice = monthly_basis(position, Quote(INSTRUMENT, Decimal(12), NOW, "test"), None)
    assert price == Decimal(10) and day is None and "不是严格月收益" in notice


def snapshot(day):
    p = Decimal(12)
    bar = PriceBar(INSTRUMENT, date(2026, 10, day), p, p, p, p, Decimal(100))
    return ClosingPrices(INSTRUMENT, "test:close_unadjusted", NOW, (bar,))


@pytest.mark.asyncio
async def test_same_session_cache_reused_after_fetch_failure(monkeypatch):
    saved = snapshot(19)
    cache = AsyncMock()
    cache.get.return_value = saved
    monkeypatch.setattr(
        module, "_fetch_closing_quote_and_bars", AsyncMock(side_effect=RuntimeError("offline"))
    )
    quote, bars, note = await module.closing_quote_and_bars(INSTRUMENT, NOW, cache)
    assert quote.last_price == Decimal(12) and bars == saved.bars
    assert quote.source.endswith(":cached") and "2026-10-19" in note
    cache.save.assert_not_awaited()


@pytest.mark.asyncio
async def test_previous_session_cache_not_used_as_today(monkeypatch):
    cache = AsyncMock()
    cache.get.return_value = snapshot(16)
    monkeypatch.setattr(
        module, "_fetch_closing_quote_and_bars", AsyncMock(side_effect=RuntimeError("offline"))
    )
    with pytest.raises(RuntimeError, match="offline"):
        await module.closing_quote_and_bars(INSTRUMENT, NOW, cache)


@pytest.mark.asyncio
async def test_success_persisted_and_storage_failure_does_not_erase_price(monkeypatch):
    saved = snapshot(19)
    quote = Quote(INSTRUMENT, Decimal(12), NOW, saved.source)
    monkeypatch.setattr(
        module, "_fetch_closing_quote_and_bars", AsyncMock(return_value=(quote, saved.bars, "ok"))
    )
    cache = AsyncMock()
    assert (await module.closing_quote_and_bars(INSTRUMENT, NOW, cache))[0] == quote
    cache.save.assert_awaited_once_with(saved)
    cache.save.side_effect = RuntimeError("db offline")
    assert "缓存保存失败" in (await module.closing_quote_and_bars(INSTRUMENT, NOW, cache))[2]
