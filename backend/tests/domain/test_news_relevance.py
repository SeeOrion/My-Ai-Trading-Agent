from datetime import UTC, datetime, timedelta
from decimal import Decimal

from ai_trading_agent.domain.aggregate.news import NewsArticle
from ai_trading_agent.domain.service.news_relevance import NewsSubject, analyze_relevant_news

NOW = datetime(2026, 11, 9, 4, tzinfo=UTC)
SUBJECT = NewsSubject("600737.SH", ("中粮糖业",), ("食品",), "test")


def article(title, content="", *, age=0, publisher="test"):
    return NewsArticle(title, content or title, publisher, NOW - timedelta(hours=age))


def test_unrelated_good_news_is_not_good_stock_sentiment():
    result = analyze_relevant_news(
        SUBJECT, [article("其他公司利润增长"), article("央行降息，上证指数上涨")], now=NOW
    )
    assert result["instrument"]["label"] == "unavailable"
    assert result["score"] is None
    assert result["market"]["label"] == "positive"


def test_name_code_industry_and_local_sentence_attribution():
    result = analyze_relevant_news(
        SUBJECT,
        [
            article("中粮糖业亏损", "中粮糖业亏损。其他公司上涨盈利增长回购。"),
            article("股票600737下跌"),
            article("食品行业盈利增长"),
            article("其他公司6007370增长"),
            article("金额600737.01亿元"),
        ],
        now=NOW,
    )
    assert result["instrument"]["articles"] == 2
    assert result["industry"]["articles"] == 1
    assert result["score"] == Decimal(-1)
    assert result["factor_eligible"] is True
    assert result["instrument"]["evidence"][0]["matched_terms"]


def test_duplicate_stale_and_future_news_cannot_make_factor_eligible():
    result = analyze_relevant_news(
        SUBJECT,
        [
            article("中粮糖业增长"),
            article("中粮糖业增长", publisher="syndicated"),
            article("中粮糖业回购", age=25),
            article("中粮糖业盈利", age=-1),
        ],
        now=NOW,
    )
    assert result["instrument"]["articles"] == 1
    assert result["factor_eligible"] is False
    assert result["score"] is None


def test_ambiguous_us_ticker_requires_explicit_marker():
    result = analyze_relevant_news(
        NewsSubject("US.ON"), [article("ON sales growth"), article("$ON growth")], now=NOW
    )
    assert result["instrument"]["articles"] == 1


def test_industry_never_fills_missing_direct_sentiment():
    result = analyze_relevant_news(SUBJECT, [article("食品增长"), article("食品盈利")], now=NOW)
    assert result["industry"]["label"] == "positive"
    assert result["score"] is None
