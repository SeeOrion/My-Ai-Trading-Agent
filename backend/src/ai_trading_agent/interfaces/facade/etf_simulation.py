"""Compose ETF-only screening from the user's watchlist and shared quote service."""
import asyncio
from ai_trading_agent.application.candidates import rank_quotes
from ai_trading_agent.domain.enums.candidates import CandidateRanking
from ai_trading_agent.domain.enums.market import InstrumentType, Market
from ai_trading_agent.interfaces.facade.portfolio import watchlist_repository
from ai_trading_agent.interfaces.facade.research_workspace import latest_quote


async def etf_candidates(app):
    items = await watchlist_repository(app).list()
    instruments = {item.instrument.symbol: item.instrument for item in items
                   if item.instrument.market is Market.A_SHARE
                   and item.instrument.instrument_type is InstrumentType.ETF}
    quotes, notices = [], []
    if not instruments:
        notices.append("没有自选场内 ETF：请先在自选跟踪添加 A 股市场、ETF 类别的标的；本轮不买入股票或场外基金。")
    for instrument in list(instruments.values())[:50]:
        try:
            quote = await asyncio.wait_for(latest_quote(instrument), timeout=15)
            if quote.instrument != instrument or quote.last_price <= 0:
                raise ValueError("ETF 行情标的或价格不匹配")
            quotes.append(quote)
        except Exception:
            notices.append(f"{instrument.symbol} ETF 行情暂不可用，本轮跳过，不使用股票替代。")
    if len(instruments) > 50:
        notices.append("本轮最多读取最近添加或更新的 50 只自选 ETF。")
    return rank_quotes(quotes, CandidateRanking.BALANCED_ENTRY), notices
