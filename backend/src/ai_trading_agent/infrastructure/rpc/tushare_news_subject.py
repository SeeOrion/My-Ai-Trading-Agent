"""Read verified A-share name/industry metadata, not paid Tushare news."""

import asyncio

from ai_trading_agent.domain.aggregate.market import Instrument
from ai_trading_agent.domain.service.news_relevance import NewsSubject
from ai_trading_agent.infrastructure.config.providers import TushareSettings


class TushareNewsSubjectProvider:
    def __init__(self, settings: TushareSettings):
        self._settings = settings

    async def resolve(self, instrument: Instrument) -> NewsSubject | None:
        return await asyncio.to_thread(self._resolve, instrument)

    def _resolve(self, instrument):
        import tushare as ts

        code = instrument.symbol
        client = ts.pro_api(self._settings.token, timeout=5)
        frame = client.stock_basic(ts_code=code, fields="ts_code,symbol,name,industry")
        if frame is None or frame.empty:
            return None
        matches = (
            frame[frame["ts_code"].astype(str) == code]
            if "." in code
            else frame[frame["symbol"].astype(str) == code]
        )
        if len(matches) != 1:
            return None
        row = matches.iloc[0]

        def values(key):
            value = str(row.get(key, "")).strip()
            return () if value.lower() in {"", "nan", "none"} else (value,)

        return NewsSubject(
            str(row["ts_code"]), values("name"), values("industry"), "tushare_stock_basic"
        )
