from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from ai_trading_agent.domain.aggregate.market import Instrument
from ai_trading_agent.domain.enums.market import Market
from ai_trading_agent.infrastructure.config.providers import TencentQuoteSettings
from ai_trading_agent.infrastructure.rpc.akshare_news import AkshareNewsProvider
from ai_trading_agent.infrastructure.rpc.tencent_market import TencentQuoteMarketDataProvider


class FakeFrame:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = rows
        self.empty = not rows

    def to_dict(self, *, orient: str) -> list[dict[str, object]]:
        assert orient == "records"
        return self._rows


@pytest.mark.asyncio
async def test_tencent_adapter_normalizes_an_a_share_quote() -> None:
    provider = TencentQuoteMarketDataProvider(
        TencentQuoteSettings(),
        response_fetcher=lambda url, timeout: (
            'v_sh600519="51~贵州茅台~600519~1330.00~1298.88~1295.88~45415~0~0'
            '~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~20260904150000'
            '~0~0~1338.86~1295.60";'
        ).encode("gbk"),
    )

    quote = (await provider.get_latest_quotes([Instrument("600519.SH", Market.A_SHARE)]))[0]

    assert quote.source == "tencent_public"
    assert quote.last_price == Decimal("1330.00")
    assert quote.previous_close == Decimal("1298.88")


@pytest.mark.asyncio
async def test_tencent_adapter_normalizes_hong_kong_and_us_quotes() -> None:
    provider = TencentQuoteMarketDataProvider(
        TencentQuoteSettings(),
        response_fetcher=lambda url, timeout: (
            'v_hk00700="100~腾讯控股~00700~442.800~433.000~442.400~24025286~0~0'
            '~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~2026/09/04 16:08:06'
            '~9.800~2.26~447.600~440.000";'
            'v_usAAPL="200~苹果~AAPL.OQ~328.21~324.96~324.87~37225838~0~0'
            '~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~2026-09-03 16:00:01'
            '~3.25~1.00~330.81~324.11";'
        ).encode("gbk"),
    )

    quotes = await provider.get_latest_quotes(
        [Instrument("00700", Market.HONG_KONG), Instrument("AAPL", Market.UNITED_STATES)]
    )

    assert [quote.instrument.currency for quote in quotes] == ["HKD", "USD"]
    assert [quote.last_price for quote in quotes] == [Decimal("442.800"), Decimal("328.21")]


@pytest.mark.asyncio
async def test_akshare_news_adapter_keeps_recent_source_attribution() -> None:
    now = datetime.now(UTC)
    provider = AkshareNewsProvider(
        fetchers={
            "eastmoney": lambda: FakeFrame(
                [
                    {
                        "标题": "业绩预告发布",
                        "摘要": "公司公布新的业绩预告。",
                        "发布时间": now.isoformat(),
                        "文章来源": "东方财富",
                        "新闻链接": "https://news.example/article",
                    },
                    {
                        "标题": "过期资讯",
                        "摘要": "不应返回。",
                        "发布时间": "2020-01-01T00:00:00+00:00",
                    },
                ]
            )
        }
    )

    articles = await provider.fetch_latest(sources=["eastmoney"], lookback=timedelta(hours=24))

    assert len(articles) == 1
    assert articles[0].publisher == "东方财富"
    assert articles[0].url == "https://news.example/article"
