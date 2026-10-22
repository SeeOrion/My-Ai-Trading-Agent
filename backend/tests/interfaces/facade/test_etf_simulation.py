from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from ai_trading_agent.domain.aggregate.ai_simulation import AiSimulationPortfolio
from ai_trading_agent.domain.aggregate.market import Instrument, Quote
from ai_trading_agent.domain.enums.market import InstrumentType, Market
from ai_trading_agent.domain.service.ai_simulation import reconfigure_simulation_portfolio
from ai_trading_agent.interfaces.facade import etf_simulation as service


@pytest.mark.asyncio
async def test_etf_screen_excludes_stocks_and_otc_funds(monkeypatch):
    etf = Instrument("510300.SH", Market.A_SHARE, InstrumentType.ETF)
    instruments = [etf, etf, Instrument("600519.SH", Market.A_SHARE),
                   Instrument("002010", Market.FUND, InstrumentType.FUND)]
    repo = SimpleNamespace(list=AsyncMock(return_value=[SimpleNamespace(instrument=i) for i in instruments]))
    monkeypatch.setattr(service, "watchlist_repository", lambda app: repo)
    provider = AsyncMock(return_value=Quote(etf, Decimal("4"), datetime.now(UTC), "test"))
    monkeypatch.setattr(service, "latest_quote", provider)
    screen, notices = await service.etf_candidates(None)
    provider.assert_awaited_once_with(etf)
    assert len(screen.candidates) == 1
    assert screen.candidates[0].observation.instrument == etf
    assert not notices


@pytest.mark.asyncio
async def test_empty_etf_watchlist_does_not_fall_back_to_stocks(monkeypatch):
    monkeypatch.setattr(service, "watchlist_repository", lambda app: SimpleNamespace(list=AsyncMock(return_value=[])))
    screen, notices = await service.etf_candidates(None)
    assert not screen.candidates
    assert "没有自选场内 ETF" in notices[0]


@pytest.mark.asyncio
async def test_failed_etf_quote_reports_gap(monkeypatch):
    etf = Instrument("510300.SH", Market.A_SHARE, InstrumentType.ETF)
    monkeypatch.setattr(service, "watchlist_repository", lambda app: SimpleNamespace(list=AsyncMock(return_value=[SimpleNamespace(instrument=etf)])))
    monkeypatch.setattr(service, "latest_quote", AsyncMock(side_effect=RuntimeError("offline")))
    screen, notices = await service.etf_candidates(None)
    assert not screen.candidates
    assert "行情暂不可用" in notices[0]


def test_etf_account_is_preserved_on_settings_change():
    account = AiSimulationPortfolio(uuid4(), "a_share", "CNY", Decimal(10000), Decimal(10000), 3, account_type="etf")
    updated = reconfigure_simulation_portfolio(account, initial_capital=Decimal(20000), max_positions=2, strategy_ids=(), open_position_count=0)
    assert updated.account_type == "etf"
    assert updated.cash_balance == Decimal(20000)


def test_etf_account_rejects_unsupported_market():
    with pytest.raises(ValueError, match="境内场内"):
        AiSimulationPortfolio(uuid4(), "fund", "CNY", Decimal(10000), Decimal(10000), 3, account_type="etf")
