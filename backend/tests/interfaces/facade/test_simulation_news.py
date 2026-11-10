from datetime import UTC, datetime
from decimal import Decimal as D
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from ai_trading_agent.domain.aggregate.ai_simulation import AiSimulationPortfolio
from ai_trading_agent.domain.aggregate.candidate import CandidateObservation, RankedCandidate
from ai_trading_agent.domain.aggregate.market import Instrument
from ai_trading_agent.domain.enums.market import Market
from ai_trading_agent.interfaces.facade import ai_simulation as service
from ai_trading_agent.interfaces.facade import news_research


@pytest.mark.asyncio
async def test_simulated_buy_receives_scoped_news_and_preserves_discipline_veto(monkeypatch):
    news = {
        "scope": "instrument",
        "score": D("0.8"),
        "factor_eligible": True,
        "summary": "个股2条；大盘积极",
    }
    monkeypatch.setattr(news_research, "instrument_news_research", AsyncMock(return_value=news))
    factors = AsyncMock(
        return_value={
            "observations": [
                {
                    "identifier": "news_sentiment",
                    "direction": "supportive",
                    "interpretation": "个股积极",
                }
            ]
        }
    )
    monkeypatch.setattr(service, "builtin_factor_analysis", factors)
    monkeypatch.setattr(
        service, "_discipline_entry_blockers", AsyncMock(return_value=("个人纪律禁止买入",))
    )
    candidate = RankedCandidate(
        CandidateObservation(
            Instrument("600737.SH", Market.A_SHARE),
            "中粮糖业",
            D(10),
            D(1),
            D(10000),
            D(11),
            D(9),
            datetime.now(UTC),
            "test",
        ),
        D(80),
        ("test",),
    )
    portfolio = AiSimulationPortfolio(uuid4(), "a_share", "CNY", D(100000), D(100000), 3)
    simulated, decision = await service._assess_entry_rules(
        object(), candidate, portfolio, (), 0
    )
    assert factors.call_args.kwargs["news_sentiment"] == news
    assert news["summary"] in simulated.rationale
    assert decision.allocation is None
    assert "个人纪律禁止买入" in decision.blockers
    report = service._decision_report(simulated, decision)
    assert news["summary"] in report.research_notes
