from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ai_trading_agent.domain.aggregate.instrument_identity import CatalogInstrument
from ai_trading_agent.domain.aggregate.market_brief import (
    IndexSnapshot,
    PostMarketBrief,
    SectorPerformance,
)
from ai_trading_agent.interfaces.facade import market_assistant
from ai_trading_agent.interfaces.model.http import NewsItemResponse


@pytest.mark.asyncio
async def test_topic_question_uses_bounded_source_context_and_clean_model_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime(2026, 9, 13, tzinfo=UTC)
    brief = PostMarketBrief(
        observed_at=now,
        source="hithink_finance_index",
        indices=(
            IndexSnapshot("000001.SH", "上证综指", Decimal("3000"), None, Decimal("0.3")),
        ),
        leading_sectors=(
            SectorPerformance("886001.TI", "电子", Decimal("1200"), Decimal("1.2")),
        ),
        lagging_sectors=(
            SectorPerformance("886002.TI", "银行", Decimal("900"), Decimal("-0.4")),
        ),
    )

    async def fake_brief() -> PostMarketBrief:
        return brief

    async def fake_news(_: list[str]) -> list[NewsItemResponse]:
        return [
            NewsItemResponse(
                title="科技板块资讯",
                content="公开资讯摘要",
                publisher="eastmoney",
                published_at=now.isoformat(),
                url=None,
                sentiment="positive",
                sentiment_score=Decimal("0.4"),
            )
        ]

    async def fake_catalogue(
        query: str, *, asset_types: tuple[str, ...], limit: int
    ) -> list[CatalogInstrument]:
        assert query == "科技"
        assert asset_types == ("a-share",)
        assert limit == 6
        return [
            CatalogInstrument(
                symbol="688001.SH",
                name="科技样本",
                asset_type="a-share",
                exchange="SH",
                currency="CNY",
                source="hithink_finance_meta",
            )
        ]

    async def fake_model(question: str, context: str) -> str:
        assert "科技样本" in context
        assert "上证综指" in context
        return "**结论：** 已使用当前数据。\n*相关候选：* 科技样本（688001.SH）。"

    monkeypatch.setattr(market_assistant, "post_market_brief", fake_brief)
    monkeypatch.setattr(market_assistant, "latest_news", fake_news)
    monkeypatch.setattr(market_assistant, "search_instrument_catalog", fake_catalogue)
    monkeypatch.setattr(market_assistant, "_model_answer", fake_model)

    result = await market_assistant.answer_market_question("我想投资科技，都有哪些股票？")

    assert result.candidates[0].symbol == "688001.SH"
    assert "同花顺标的目录" in result.sources
    assert "**" not in result.answer
    assert result.answer.startswith("结论：")


def test_topic_extraction_preserves_the_investment_theme() -> None:
    assert market_assistant._catalogue_spec("白糖都有哪些 ETF 可以了解？") == (
        "白糖",
        ("fund-etf", "fund-lof"),
    )
