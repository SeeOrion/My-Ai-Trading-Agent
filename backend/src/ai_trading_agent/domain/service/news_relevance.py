"""Explainable news attribution, independent of providers, UI and trading accounts."""

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from ai_trading_agent.domain.aggregate.news import NewsArticle
from ai_trading_agent.domain.aggregate.research import analyze_financial_sentiment


@dataclass(frozen=True, slots=True)
class NewsSubject:
    symbol: str
    names: tuple[str, ...] = ()
    industries: tuple[str, ...] = ()
    source: str = "code_only"


MACRO_TERMS = (
    "上证指数",
    "沪指",
    "深成指",
    "创业板指",
    "沪深300",
    "恒生指数",
    "纳斯达克",
    "标普500",
    "道琼斯",
    "央行",
    "美联储",
    "降息",
    "加息",
    "货币政策",
)


def _match(text: str, term: str) -> bool:
    if not term:
        return False
    if re.fullmatch(r"[a-zA-Z0-9.$:]+", term):
        # Bare short English tickers (A, ON, CAT) are ambiguous ordinary words.
        return (
            re.search(r"(?<![a-zA-Z0-9.])" + re.escape(term) + r"(?![a-zA-Z0-9.])", text, re.I)
            is not None
        )
    return term.casefold() in text.casefold()


def _terms(subject: NewsSubject) -> tuple[str, ...]:
    symbol = subject.symbol.upper()
    parts = symbol.split(".")
    code = parts[-1] if parts[0] in {"US", "HK", "SH", "SZ", "BJ"} else parts[0]
    codes = [symbol] if "." in symbol else []
    if code.isdigit() and len(code) >= 5:
        codes.append(code)
    elif code.isalpha():
        codes.extend((f"${code}", f"NASDAQ:{code}", f"NYSE:{code}"))
    return tuple(dict.fromkeys([*codes, *(n for n in subject.names if len(n.strip()) >= 2)]))


def _layer(items: list[tuple[NewsArticle, list[str], str]]) -> dict:
    scores = [analyze_financial_sentiment(text) for _, _, text in items]
    score = sum((s.score for s in scores), Decimal(0)) / len(scores) if scores else None
    label = (
        "unavailable"
        if score is None
        else "positive"
        if score >= Decimal("0.2")
        else "negative"
        if score <= Decimal("-0.2")
        else "neutral"
    )
    return {
        "label": label,
        "score": score,
        "articles": len(items),
        "positive_terms": sorted({t for s in scores for t in s.positive_terms}),
        "negative_terms": sorted({t for s in scores for t in s.negative_terms}),
        "evidence": [
            {
                "title": a.title,
                "publisher": a.publisher,
                "url": a.url,
                "published_at": a.published_at.isoformat(),
                "matched_terms": terms,
                "excerpt": text[:300],
            }
            for a, terms, text in items[:5]
        ],
    }


def analyze_relevant_news(
    subject: NewsSubject, articles: list[NewsArticle], *, now: datetime
) -> dict:
    """Use 24h dated news, deduplicate syndicated titles, score matched sentences only.

    At least two distinct direct items are needed for the trading factor. Macro
    and industry sentiment remain context, never substitutes for direct evidence.
    """
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    groups: dict[str, list] = {"instrument": [], "industry": [], "market": []}
    seen: set[str] = set()
    direct_titles = []
    count = 0
    for article in sorted(articles, key=lambda a: a.published_at, reverse=True):
        identity = re.sub(r"\W+", "", article.title.casefold())
        if identity in seen or not now - timedelta(
            hours=24
        ) <= article.published_at <= now + timedelta(minutes=5):
            continue
        seen.add(identity)
        count += 1
        text = re.sub(r"<[^>]+>", " ", f"{article.title}。{article.content}")
        direct = [term for term in _terms(subject) if _match(text, term)]
        sector = [term for term in subject.industries if len(term) >= 2 and _match(text, term)]
        macro = [term for term in MACRO_TERMS if _match(text, term)]
        for group, matched in (
            ("instrument", direct),
            ("industry", sector if not direct else []),
            ("market", macro),
        ):
            if matched:
                snippets = [
                    s.strip()
                    for s in re.split(r"[。！？；\n]|(?<=\.)\s+", text)
                    if any(_match(s, term) for term in matched)
                ]
                groups[group].append((article, matched, "。".join(dict.fromkeys(snippets))))
        if direct:
            direct_titles.append(article.title)
    result = {name: _layer(items) for name, items in groups.items()}
    direct = result["instrument"]
    eligible = direct["articles"] >= 2
    labels = {
        "positive": "积极",
        "negative": "消极",
        "neutral": "中性",
        "unavailable": "暂无相关资讯",
    }
    result.update(
        {
            "scope": "instrument",
            "source": "public_news_relevance_v1",
            "subject": {
                "symbol": subject.symbol,
                "names": list(subject.names),
                "industries": list(subject.industries),
                "source": subject.source,
            },
            "label": direct["label"],
            "score": direct["score"] if eligible else None,
            "articles": direct["articles"],
            "titles": direct_titles,
            "factor_eligible": eligible,
            "sample_articles": count,
            "summary": f"近24小时：个股{labels[direct['label']]}（{direct['articles']}条），行业{labels[result['industry']['label']]}（{result['industry']['articles']}条），大盘{labels[result['market']['label']]}（{result['market']['articles']}条）。"
            + (
                "个股情绪可参与所选策略的新闻因子。"
                if eligible
                else "个股证据不足两条，新闻因子暂缺，不等同于利空。"
            ),
        }
    )
    return result
