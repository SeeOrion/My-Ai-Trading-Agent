import { FormEvent, useEffect, useState } from "react";
import {
  createDiscipline, createStrategy, Discipline, DisciplineInput, fetchDisciplines,
  fetchFactors, fetchNews, fetchQuote, fetchResearch, fetchStrategies, Factor, Market, NewsItem,
  ResearchReport, Strategy, StrategyInput, updateDiscipline, InstrumentType, FundResearch, fetchFundResearch,
  updateStrategy, fetchTechnicalStudy, TechnicalStudy, TechnicalTimeframe, WatchlistInput, WatchlistItem,
  createWatchlistItem, deleteWatchlistItem, fetchWatchlist, PaperPositionInput, PaperPosition,
  createPaperPosition, deletePaperPosition, fetchPaperPositions, fetchPaperPortfolioOverview, PaperPortfolioOverview, PaperPositionValuation,
  AiSimulationOverview, fetchAiSimulationOverview, runAiSimulation,
  fetchWatchlistAnalyses, fetchWatchlistAnalysis, refreshWatchlistAnalysis, WatchlistAnalysis, Quote,
  fetchWatchlistDeepDive, WatchlistFinancialDetail, fetchPostMarketBrief, PostMarketBrief, resolveInstrument,
  askMarketQuestion, MarketQuestionAnswer
} from "./api";

type Page = "dashboard" | "watchlist" | "positions" | "funds" | "strategies" | "disciplines" | "documents" | "journal" | "settings";

const navigation: Array<{ id: Page; label: string; description: string }> = [
  { id: "dashboard", label: "总览", description: "盘后快报、指数总览、板块轮动与财经资讯" },
  { id: "watchlist", label: "自选跟踪", description: "研究分析与单标的深度跟踪" },
  { id: "positions", label: "模拟持仓", description: "手动成本、数量与未实现盈亏" },
  { id: "funds", label: "基金 / ETF", description: "净值、收益、持仓、回撤与基金资讯" },
  { id: "strategies", label: "个人策略", description: "编辑、注入、版本" },
  { id: "disciplines", label: "个人纪律", description: "价位、仓位与退出规则" },
  { id: "documents", label: "文档 / OCR", description: "研报与证据提取" },
  { id: "journal", label: "交易日志", description: "导入、归因、复盘" },
  { id: "settings", label: "设置", description: "私有部署与连接配置" }
];

const defaultStrategy: StrategyInput = {
  name: "我的研究策略", thesis: "关注高质量、估值合理且有正向新闻催化的标的。",
  factor_ids: ["momentum_20d", "return_on_equity"], markets: ["a_share"],
  max_position_pct: "10", risk_notes: "分散持仓，避免追高。", status: "draft"
};

const defaultDiscipline: DisciplineInput = {
  name: "分批交易纪律", symbol: "600519.SH", market: "a_share", instrument_type: "equity",
  buy_price: "15", add_price: "16", take_profit_price: "16.5", exit_price: "14.5",
  notes: "仅在自己复核后手动执行；纪律不连接券商，也不会自动下单。", status: "active"
};

function App() {
  const [page, setPage] = useState<Page>("dashboard");
  const [factors, setFactors] = useState<Factor[]>([]);
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [strategyError, setStrategyError] = useState<string | null>(null);
  const [disciplines, setDisciplines] = useState<Discipline[]>([]);
  const [disciplineError, setDisciplineError] = useState<string | null>(null);

  useEffect(() => { fetchFactors().then(setFactors).catch(() => undefined); }, []);
  const reloadStrategies = () => fetchStrategies().then(setStrategies).catch((error: Error) => setStrategyError(error.message));
  useEffect(() => { reloadStrategies(); }, []);
  const reloadDisciplines = () => fetchDisciplines().then(setDisciplines).catch((error: Error) => setDisciplineError(error.message));
  useEffect(() => { reloadDisciplines(); }, []);

  const active = navigation.find((item) => item.id === page)!;
  return <main className="shell">
    <aside className="sidebar">
      <div className="brand"><span>◈</span><div><strong>My AI</strong><small>Trading Agent</small></div></div>
      <nav aria-label="功能导航">{navigation.map((item) => <button key={item.id} className={page === item.id ? "nav active" : "nav"} onClick={() => setPage(item.id)}>{item.label}</button>)}</nav>
      <div className="security">私有模式<br /><small>密钥只在后端环境中使用</small></div>
    </aside>
    <section className="content">
      <header><div><p className="eyebrow">RESEARCH WORKSPACE</p><h1>{active.label}</h1><p>{active.description}</p></div><span className="pill">本机服务已连接</span></header>
      {page === "dashboard" && <Dashboard />}
      {page === "watchlist" && <WatchlistWorkspace />}
      {page === "positions" && <PaperPortfolioWorkspace strategies={strategies} />}
      {page === "funds" && <FundWorkspace />}
      {page === "strategies" && <StrategyWorkspace factors={factors} strategies={strategies} error={strategyError} reload={reloadStrategies} />}
      {page === "disciplines" && <DisciplineWorkspace disciplines={disciplines} error={disciplineError} reload={reloadDisciplines} />}
      {["documents", "journal", "settings"].includes(page) && <FutureWorkspace page={active.label} />}
    </section>
  </main>;
}

function TickerFields({ symbol, market, instrumentType = "equity", setSymbol, setMarket }: { symbol: string; market: Market; instrumentType?: InstrumentType; setSymbol: (value: string) => void; setMarket: (value: Market) => void }) {
  const [displayName, setDisplayName] = useState<string | null>(null);
  useEffect(() => {
    const query = symbol.trim();
    if (query.length < 4) { setDisplayName(null); return; }
    let active = true;
    const timeout = window.setTimeout(() => {
      void resolveInstrument(query, market, instrumentType)
        .then((identity) => { if (active) setDisplayName(identity.display_name); })
        .catch(() => { if (active) setDisplayName(null); });
    }, 350);
    return () => { active = false; window.clearTimeout(timeout); };
  }, [symbol, market, instrumentType]);
  return <div className="ticker-fields"><div className="form-row"><label>代码<input value={symbol} onChange={(event) => setSymbol(event.target.value)} placeholder="股票填 600737；ETF 填 510300.SH；基金填 025480.OF" /></label><label>市场<select value={market} onChange={(event) => setMarket(event.target.value as Market)}><option value="a_share">A 股</option><option value="hong_kong">港股</option><option value="united_states">美股</option><option value="fund">场外基金</option></select></label></div>{displayName && <p className="identity-hint">识别标的：<strong>{displayName}</strong> · {symbol.trim().toUpperCase()}</p>}</div>;
}

function InstrumentTypeField({ value, setValue }: { value: InstrumentType; setValue: (value: InstrumentType) => void }) {
  return <label>类别<select value={value} onChange={(event) => setValue(event.target.value as InstrumentType)}><option value="equity">股票</option><option value="etf">ETF（场内）</option><option value="fund">公募基金（场外）</option></select></label>;
}

function Dashboard() {
  const [brief, setBrief] = useState<PostMarketBrief | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  async function load(refresh = false) {
    setLoading(true); setError(null);
    try { setBrief(await fetchPostMarketBrief(refresh)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "盘后快报请求失败"); }
    finally { setLoading(false); }
  }
  useEffect(() => { void load(); }, []);
  return <><section className="hero"><div><p className="eyebrow">POST-MARKET BRIEF</p><h2>今日市场快报</h2><p>从同花顺指数快照汇总主要指数和行业板块涨跌。盘中访问时为最新快照，收盘后可作为当日复盘入口。</p></div><button className="primary" onClick={() => void load(true)} disabled={loading}>{loading ? "更新中…" : "刷新快报"}</button></section>
    <section className="dashboard-layout"><div className="dashboard-main"><section className="panel market-brief-panel"><div className="panel-head"><div><p className="eyebrow">INDEX OVERVIEW</p><h2>指数总览</h2><p>上证、深成、创业板和沪深 300。</p></div>{brief && <small className="brief-time">快照于 {new Date(brief.observed_at).toLocaleString()}</small>}</div>{error && <div className="notice">{error}</div>}{brief && <><div className="index-grid">{brief.indices.map((item) => <article className="index-card" key={item.symbol}><small>{item.name}</small><strong>{item.last_price}</strong><span className={Number(item.change_percent) > 0 ? "change up" : Number(item.change_percent) < 0 ? "change down" : "change"}>{formatPercent(item.change_percent)} {item.price_change !== null ? `(${formatSigned(item.price_change)})` : ""}</span></article>)}</div><section className="rotation-section"><div><p className="eyebrow">SECTOR ROTATION</p><h2>板块轮动</h2><p>按行业指数当日涨跌幅排序，不等同于资金流向。</p></div><div className="rotation-grid"><RotationList title="领涨板块" items={brief.leading_sectors} tone="up" /><RotationList title="领跌板块" items={brief.lagging_sectors} tone="down" /></div></section><p className="brief-note">{brief.coverage}<br />{brief.disclaimer}</p></>}</section><OverviewNews /></div><MarketAssistant /></section>
  </>;
}

const marketQuestionPrompts = ["今天市场行情如何？", "白糖有哪些 ETF 可以了解？", "我想关注科技，有哪些股票可先研究？"];

function MarketAssistant() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<MarketQuestionAnswer | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function ask(nextQuestion = question) {
    const normalized = nextQuestion.trim();
    if (normalized.length < 2) return;
    setQuestion(normalized); setLoading(true); setError(null);
    try { setAnswer(await askMarketQuestion(normalized)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "市场问答请求失败"); }
    finally { setLoading(false); }
  }

  return <aside className="panel market-assistant"><div><p className="eyebrow">AI MARKET Q&A</p><h2>问问市场</h2><p className="muted">用当前指数、板块、财经资讯和可核实的股票 / ETF 目录，帮你快速梳理问题。</p></div><div className="assistant-prompts">{marketQuestionPrompts.map((prompt) => <button className="prompt-chip" type="button" key={prompt} onClick={() => void ask(prompt)} disabled={loading}>{prompt}</button>)}</div><form className="assistant-form" onSubmit={(event) => { event.preventDefault(); void ask(); }}><label>你的问题<textarea value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="例如：今天市场行情如何？白糖有哪些 ETF？" maxLength={500} /></label><button className="primary" disabled={loading || question.trim().length < 2}>{loading ? "正在整理市场数据…" : "开始提问"}</button></form>{error && <div className="notice">{error}</div>}{answer && <section className="assistant-result" aria-live="polite"><div className="assistant-result-head"><strong>市场研究答复</strong><small>{new Date(answer.generated_at).toLocaleTimeString()}</small></div><AssistantAnswerText answer={answer.answer} />{answer.candidates.length > 0 && <div className="assistant-candidates"><h3>相关候选</h3><div>{answer.candidates.map((item) => <span className="candidate-chip" key={`${item.symbol}-${item.asset_type}`}><strong>{item.name}</strong><small>{item.symbol} · {marketAssetType(item.asset_type)}</small></span>)}</div></div>}{answer.sources.length > 0 && <div className="assistant-sources"><span>已用数据</span>{answer.sources.map((source) => <small key={source}>{source}</small>)}</div>}{answer.notices.map((notice) => <p className="assistant-notice" key={notice}>{notice}</p>)}</section>}</aside>;
}

function AssistantAnswerText({ answer }: { answer: string }) {
  const lines = answer.split(/\r?\n/).map(cleanResearchLine).filter(Boolean);
  return <div className="assistant-answer">{lines.map((line, index) => { const matched = line.match(/^([^：:]{2,10})[：:]\s*(.+)$/); return matched ? <div className="assistant-answer-row" key={`${index}-${line}`}><strong>{matched[1]}</strong><p>{matched[2]}</p></div> : <p key={`${index}-${line}`}>{line}</p>; })}</div>;
}

function marketAssetType(value: string) {
  return ({ "a-share": "A 股", "fund-etf": "ETF", "fund-lof": "LOF", "fund-otc": "公募基金" } as Record<string, string>)[value] ?? value;
}

function RotationList({ title, items, tone }: { title: string; items: PostMarketBrief["leading_sectors"]; tone: "up" | "down" }) {
  return <section className={`rotation-list ${tone}`}><h3>{title}</h3>{items.map((item) => <article key={item.symbol}><div><strong>{item.name}</strong><small>{item.symbol}</small></div><span className={`change ${tone}`}>{formatPercent(item.change_percent)}</span></article>)}</section>;
}

function formatPercent(value: string | null) {
  if (value === null) return "--";
  const number = Number(value);
  return `${number > 0 ? "+" : ""}${number.toFixed(2)}%`;
}

function formatSigned(value: string) {
  const number = Number(value);
  return `${number > 0 ? "+" : ""}${number.toFixed(2)}`;
}

function OverviewNews() {
  const [news, setNews] = useState<NewsItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true); setError(null);
    try { setNews(await fetchNews()); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "资讯请求失败"); }
    finally { setLoading(false); }
  }

  useEffect(() => { void load(); }, []);
  return <section className="panel overview-news"><div className="panel-head"><div><p className="eyebrow">MARKET NEWS</p><h2>财经资讯</h2><p>东方财富优先，失败时自动尝试新浪；成功结果短时缓存，并用于自选标的的情绪研究。</p></div><button className="secondary" onClick={() => void load()} disabled={loading}>{loading ? "采集中…" : "刷新资讯"}</button></div>{error && <div className="notice">{error}</div>}<div className="news-list">{news.slice(0, 6).map((item) => <article className="news-item" key={`${item.publisher}-${item.published_at}-${item.title}`}><span className={`tag ${item.sentiment}`}>{item.sentiment}</span><h3>{item.title}</h3><p>{item.content}</p><small>{item.publisher} · {new Date(item.published_at).toLocaleString()} · 情绪 {item.sentiment_score}</small></article>)}</div>{!loading && !error && news.length === 0 && <p className="muted">暂未获得可展示的公开财经资讯。</p>}</section>;
}

const defaultWatchlist: WatchlistInput = { symbol: "600519.SH", market: "a_share", instrument_type: "equity", label: "", notes: "" };
const defaultPaperPosition: PaperPositionInput = { symbol: "600519.SH", market: "a_share", instrument_type: "equity", quantity: "100", average_cost: "100", notes: "仅用于模拟，不连接券商。" };

function technicalBarLimit(timeframe: TechnicalTimeframe) {
  return timeframe === "1m" ? 1_200 : timeframe === "1w" ? 420 : 180;
}

function WatchlistWorkspace() {
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [analyses, setAnalyses] = useState<WatchlistAnalysis[]>([]);
  const [form, setForm] = useState(defaultWatchlist);
  const [message, setMessage] = useState<string | null>(null);
  const [selected, setSelected] = useState<WatchlistItem | null>(null);
  const [quote, setQuote] = useState<Quote | null>(null);
  const [report, setReport] = useState<ResearchReport | null>(null);
  const [study, setStudy] = useState<TechnicalStudy | null>(null);
  const [timeframe, setTimeframe] = useState<TechnicalTimeframe>("1d");
  const [deepDive, setDeepDive] = useState<WatchlistFinancialDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  async function load() {
    try {
      const [watchlist, savedAnalyses] = await Promise.all([
        fetchWatchlist(),
        fetchWatchlistAnalyses().catch(() => [] as WatchlistAnalysis[])
      ]);
      setItems(watchlist);
      setAnalyses(savedAnalyses);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "自选列表读取失败");
    }
  }

  useEffect(() => { void load(); }, []);

  async function save(event: FormEvent) {
    event.preventDefault();
    try {
      await createWatchlistItem(form);
      setForm(defaultWatchlist);
      setMessage("已加入自选。后台将仅对你的自选标的定时更新标签与 AI 解读。");
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "保存失败");
    }
  }

  async function remove(itemId: string) {
    try {
      await deleteWatchlistItem(itemId);
      if (selected?.item_id === itemId) {
        setSelected(null); setQuote(null); setReport(null); setStudy(null); setDeepDive(null);
      }
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "删除失败");
    }
  }

  async function selectItem(item: WatchlistItem) {
    setSelected(item); setQuote(null); setReport(null); setStudy(null); setDeepDive(null); setDetailLoading(true); setMessage(null);
    const [quoteResult, researchResult, studyResult, analysisResult, deepDiveResult] = await Promise.allSettled([
      fetchQuote(item.symbol, item.market, item.instrument_type),
      fetchResearch(item.symbol, item.market, item.instrument_type),
      fetchTechnicalStudy(
        item.symbol, item.market, timeframe, item.instrument_type, technicalBarLimit(timeframe)
      ),
      fetchWatchlistAnalysis(item.item_id),
      fetchWatchlistDeepDive(item.item_id)
    ]);
    if (quoteResult.status === "fulfilled") setQuote(quoteResult.value);
    if (researchResult.status === "fulfilled") setReport(researchResult.value);
    if (studyResult.status === "fulfilled") setStudy(studyResult.value);
    if (analysisResult.status === "fulfilled") upsertAnalysis(analysisResult.value);
    if (deepDiveResult.status === "fulfilled") setDeepDive(deepDiveResult.value);
    const failures = [quoteResult, researchResult, studyResult, deepDiveResult].filter((result) => result.status === "rejected");
    if (failures.length) setMessage("部分数据暂不可用；页面已保留能够获取的研究结果。");
    setDetailLoading(false);
  }

  function upsertAnalysis(analysis: WatchlistAnalysis) {
    setAnalyses((current) => [analysis, ...current.filter((item) => item.watchlist_item_id !== analysis.watchlist_item_id)]);
  }

  async function refreshAnalysis(item: WatchlistItem) {
    setRefreshing(true); setMessage(null);
    try {
      const analysis = await refreshWatchlistAnalysis(item.item_id);
      upsertAnalysis(analysis);
      setMessage("已更新该自选标的的标签与 AI 研究摘要。");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "自选分析刷新失败");
    } finally {
      setRefreshing(false);
    }
  }

  async function changeTimeframe(nextTimeframe: TechnicalTimeframe) {
    setTimeframe(nextTimeframe);
    if (selected === null) return;
    setStudy(null); setDetailLoading(true); setMessage(null);
    try {
      setStudy(await fetchTechnicalStudy(
        selected.symbol, selected.market, nextTimeframe, selected.instrument_type,
        technicalBarLimit(nextTimeframe)
      ));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "K 线数据读取失败");
    } finally {
      setDetailLoading(false);
    }
  }

  const selectedAnalysis = selected
    ? analyses.find((item) => item.watchlist_item_id === selected.item_id) ?? null
    : null;
  return <section className="watchlist-workspace">
    <section className="portfolio-layout">
      <section className="panel"><h2>添加自选标的</h2><p>只保存你明确选择的股票、ETF 或基金；不会启动全市场扫描。</p>{message && <div className="success">{message}</div>}<form onSubmit={save}><TickerFields symbol={form.symbol} market={form.market} instrumentType={form.instrument_type} setSymbol={(symbol) => setForm({ ...form, symbol })} setMarket={(market) => setForm({ ...form, market })} /><InstrumentTypeField value={form.instrument_type} setValue={(instrument_type) => setForm({ ...form, instrument_type })} /><label>显示名称（可选）<input value={form.label} onChange={(event) => setForm({ ...form, label: event.target.value })} /></label><label>跟踪备注<textarea value={form.notes} onChange={(event) => setForm({ ...form, notes: event.target.value })} /></label><button className="primary">加入自选</button></form></section>
      <section className="panel"><div className="panel-head"><div><h2>我的自选</h2><p>点击标的展开当日成交、K 线、资金、情绪与 AI 解读。</p></div><button className="secondary" onClick={() => void load()}>刷新列表</button></div><div className="watchlist-cards">{items.map((item) => { const analysis = analyses.find((entry) => entry.watchlist_item_id === item.item_id); return <article className={selected?.item_id === item.item_id ? "watch-item selected" : "watch-item"} key={item.item_id}><button className="watch-item-main" onClick={() => void selectItem(item)}><strong>{item.label || item.display_name || item.symbol}</strong><p>{item.symbol} · {item.market} · {item.instrument_type}</p><div className="tag-list">{analysis ? analysis.tags.map((tag) => <span className={`tag ${tag.tone}`} key={tag.category}>{tag.label}</span>) : <span className="tag neutral">等待定时分析</span>}</div>{analysis && <small>更新于 {new Date(analysis.observed_at).toLocaleString()} · {analysis.status}</small>}{item.notes && <small>{item.notes}</small>}</button><div className="watch-item-actions"><button className="secondary" onClick={() => void refreshAnalysis(item)} disabled={refreshing}>{refreshing ? "分析中…" : "更新解读"}</button><button className="secondary" onClick={() => void remove(item.item_id)}>移除</button></div></article>; })}</div></section>
    </section>
    {selected && <WatchlistDetail item={selected} quote={quote} report={report} study={study} analysis={selectedAnalysis} deepDive={deepDive} timeframe={timeframe} onTimeframeChange={(value) => void changeTimeframe(value)} loading={detailLoading} onRefresh={() => void refreshAnalysis(selected)} refreshing={refreshing} />}
  </section>;
}

function WatchlistDetail({ item, quote, report, study, analysis, deepDive, timeframe, onTimeframeChange, loading, onRefresh, refreshing }: { item: WatchlistItem; quote: Quote | null; report: ResearchReport | null; study: TechnicalStudy | null; analysis: WatchlistAnalysis | null; deepDive: WatchlistFinancialDetail | null; timeframe: TechnicalTimeframe; onTimeframeChange: (value: TechnicalTimeframe) => void; loading: boolean; onRefresh: () => void; refreshing: boolean }) {
  return <section className="panel watchlist-detail"><div className="panel-head"><div><p className="eyebrow">RESEARCH ANALYSIS · DEEP TRACKING</p><h2>{item.label || item.symbol}</h2><p>研究分析与深度跟踪已合并：仅拉取此自选标的的行情、基本面、资金、资讯情绪、因子与 K 线数据。</p></div><button className="primary" onClick={onRefresh} disabled={refreshing}>{refreshing ? "正在生成摘要…" : "更新 AI 解读"}</button></div>{loading && <p className="muted">正在读取当日成交和研究数据…</p>}<div className="metric-grid"><Metric label="现价" value={quote ? `${quote.last_price} ${quote.currency}` : "—"} /><Metric label="今日成交量" value={quote?.volume ?? "—"} /><Metric label="来源" value={quote?.source ?? "—"} /><Metric label="状态" value={analysis?.status ?? "—"} /></div>{analysis && <><div className="tag-list detail-tags">{analysis.tags.map((tag) => <span className={`tag ${tag.tone}`} key={tag.category}>{tag.label}</span>)}</div>{analysis.ai_summary && <CleanResearchSummary summary={analysis.ai_summary} />}{analysis.notices.map((notice) => <div className="notice" key={notice}>{notice}</div>)}</>}{deepDive && <FinancialDeepDive detail={deepDive} />}{report && <section className="deep-research-section"><div><p className="eyebrow">RESEARCH ANALYSIS</p><h3>研究分析</h3></div><div className="research-results"><DataCard title="基本面" data={report.fundamentals} /><DataCard title="资金流" data={report.capital_flow} /><DataCard title="新闻情绪" data={report.news_sentiment} /><DataCard title="10 个内置因子" data={report.factor_analysis} /></div>{report.fund_research && <FundWatchlistDetail data={report.fund_research} />}{report.notices.map((notice) => <div className="notice" key={notice}>{notice}</div>)}</section>}<section className="deep-research-section"><div className="panel-head"><div><p className="eyebrow">DEEP TRACKING</p><h3>深度跟踪：K 线、均线与成交量</h3></div><label className="timeframe-control">周期<select value={timeframe} onChange={(event) => onTimeframeChange(event.target.value as TechnicalTimeframe)}><option value="1d">日 K</option><option value="1w">周 K</option><option value="1m">月 K</option></select></label></div>{study ? <TechnicalStudyView study={study} /> : <p className="muted">正在更新 {timeframe === "1d" ? "日 K" : timeframe === "1w" ? "周 K" : "月 K"} 数据…</p>}</section></section>;
}

function CleanResearchSummary({ summary }: { summary: string }) {
  const lines = summary.split(/\r?\n/).map(cleanResearchLine).filter(Boolean);
  return <section className="analysis-box"><h3>AI 研究摘要</h3><div className="analysis-summary">{lines.map((line, index) => <p key={`${index}-${line}`}>{line}</p>)}</div></section>;
}

function cleanResearchLine(value: string) {
  return value.replace(/\*+/g, "").replace(/_+/g, "").replace(/`+/g, "").replace(/^\s*(?:#{1,6}|[-•]|\d+[.)])\s*/, "").replace(/\s+/g, " ").trim();
}

function FinancialDeepDive({ detail }: { detail: WatchlistFinancialDetail }) {
  const income = detail.income_statement;
  const balance = detail.balance_sheet;
  const cashFlow = detail.cash_flow;
  const valuation = detail.valuation;
  const hasCompanyData = income || balance || cashFlow || valuation;
  return <section className="deep-research-section financial-deep-dive"><div><p className="eyebrow">PUBLISHED FINANCIAL DETAIL</p><h3>财务、估值与时间催化剂</h3><p className="muted">数据源：{detail.source} · 更新于 {new Date(detail.observed_at).toLocaleString()}。财报为已披露口径，时间催化剂不推断未来事件。</p></div>{hasCompanyData && <div className="financial-section-grid">{income && <FinancialMetricCard title="利润表" caption={`报告期 ${income.report_period} · 披露 ${income.announced_on}`} metrics={[['营业收入', income.operating_income], ['营业利润', income.operating_profit], ['净利润', income.net_profit], ['基本每股收益', income.basic_eps]]} />}{cashFlow && <FinancialMetricCard title="现金流" caption={`报告期 ${cashFlow.report_period}`} metrics={[['经营活动现金流', cashFlow.operating_cash_flow], ['投资活动现金流', cashFlow.investing_cash_flow], ['筹资活动现金流', cashFlow.financing_cash_flow], ['现金净增加额', cashFlow.net_cash_change]]} />}{balance && <FinancialMetricCard title="资产负债结构" caption={`报告期 ${balance.report_period}`} metrics={[['资产总计', balance.total_assets], ['负债合计', balance.total_debt], ['所有者权益', balance.total_equity], ['货币资金', balance.cash], ['应收账款', balance.accounts_receivable], ['资产负债率', balance.debt_to_assets_percent, '%']]} />}{valuation && <FinancialMetricCard title="估值定价" caption={valuation.observed_at ? `快照 ${new Date(valuation.observed_at).toLocaleString()}` : '快照时间未提供'} metrics={[['PE (TTM)', valuation.price_to_earnings_ttm], ['PE (MRQ)', valuation.price_to_earnings_mrq], ['PB (MRQ)', valuation.price_to_book_mrq], ['PS (TTM)', valuation.price_to_sales_ttm], ['PCF (TTM)', valuation.price_to_cash_flow_ttm]]} />}</div>}{detail.time_catalysts.length > 0 && <section className="catalyst-list"><h4>时间催化剂（已披露）</h4>{detail.time_catalysts.map((item) => <article className="catalyst-item" key={`${item.kind}-${item.occurred_on}-${item.title}`}><time>{item.occurred_on}</time><div><strong>{item.title}</strong><p>{item.detail}</p></div></article>)}</section>}{detail.notices.map((notice) => <div className="notice" key={notice}>{notice}</div>)}</section>;
}

function FundWatchlistDetail({ data }: { data: Record<string, unknown> }) {
  return <section className="fund-watchlist-detail"><div><p className="eyebrow">FUND / ETF DISCLOSED DATA</p><h4>基金 / ETF 披露研究</h4><p className="muted">净值、持仓、资产配置、财务与资讯均以公开披露时间为准，不代表实时持仓或资金流。</p></div><div className="financial-section-grid"><DataCard title="基本资料与最新净值" data={asRecord(data.overview)} /><DataCard title="收益与回撤" data={{ returns_percent: data.returns_percent, drawdowns_percent: data.drawdowns_percent }} /><DataCard title="重仓持仓" data={{ holdings: data.holdings }} /><DataCard title="持仓与资产配置" data={{ asset_allocations: data.asset_allocations, institutional_holding_percent: data.institutional_holding_percent }} /><DataCard title="财务与诊断" data={{ latest_financials: data.latest_financials, diagnostics: data.diagnostics }} /><DataCard title="基金资讯列表" data={{ news: data.news }} /></div>{Array.isArray(data.limitations) && data.limitations.map((notice) => <div className="notice" key={String(notice)}>{String(notice)}</div>)}</section>;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : null;
}

function FinancialMetricCard({ title, caption, metrics }: { title: string; caption: string; metrics: Array<[string, string | null, string?]> }) {
  return <article className="financial-metric-card"><h4>{title}</h4><small>{caption}</small><dl>{metrics.map(([label, value, suffix]) => <div key={label}><dt>{label}</dt><dd>{value === null ? '—' : `${formatFinancialValue(value)}${suffix ?? ''}`}</dd></div>)}</dl></article>;
}

function formatFinancialValue(value: string) {
  const number = Number(value);
  return Number.isFinite(number) ? new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 2 }).format(number) : value;
}

function PaperPortfolioWorkspace({ strategies }: { strategies: Strategy[] }) {
  const [workspace, setWorkspace] = useState<"manual" | "ai">("manual");
  return <section className="paper-portfolio-workspace"><div className="portfolio-mode-switch" role="tablist" aria-label="模拟持仓模式"><button className={workspace === "manual" ? "secondary active" : "secondary"} onClick={() => setWorkspace("manual")}>手动模拟持仓</button><button className={workspace === "ai" ? "secondary active" : "secondary"} onClick={() => setWorkspace("ai")}>AI 模拟选股与交易</button></div>{workspace === "manual" ? <ManualPaperPortfolioWorkspace /> : <AiSimulationWorkspace strategies={strategies} />}</section>;
}

function ManualPaperPortfolioWorkspace() {
  const [positions, setPositions] = useState<PaperPosition[]>([]);
  const [overview, setOverview] = useState<PaperPortfolioOverview | null>(null);
  const [form, setForm] = useState(defaultPaperPosition);
  const [message, setMessage] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const enteredCostAmount = calculatePositionCost(form.quantity, form.average_cost);
  const load = () => fetchPaperPositions().then(setPositions).catch((error: Error) => setMessage(error.message));
  async function refreshOverview() { setRefreshing(true); try { setOverview(await fetchPaperPortfolioOverview()); } catch (error) { setMessage(error instanceof Error ? error.message : "组合估值失败"); } finally { setRefreshing(false); } }
  useEffect(() => { void load(); void refreshOverview(); }, []);
  async function save(event: FormEvent) { event.preventDefault(); try { await createPaperPosition(form); setForm(defaultPaperPosition); setMessage("模拟持仓已保存；不会产生真实委托。"); await load(); await refreshOverview(); } catch (error) { setMessage(error instanceof Error ? error.message : "保存失败"); } }
  async function remove(positionId: string) { try { await deletePaperPosition(positionId); setOverview(null); await load(); await refreshOverview(); } catch (error) { setMessage(error instanceof Error ? error.message : "删除失败"); } }
  return <section className="paper-portfolio-workspace"><section className="portfolio-layout"><section className="panel"><h2>录入模拟持仓</h2><p>选择标的后填写持有股数与平均成本；成本金额会由“股数 × 平均成本”自动计算，不会产生真实委托。</p>{message && <div className="success">{message}</div>}<form onSubmit={save}><TickerFields symbol={form.symbol} market={form.market} instrumentType={form.instrument_type} setSymbol={(symbol) => setForm({ ...form, symbol })} setMarket={(market) => setForm({ ...form, market })} /><InstrumentTypeField value={form.instrument_type} setValue={(instrument_type) => setForm({ ...form, instrument_type })} /><div className="form-row"><label>持有股数<input type="number" min="0.000001" step="any" value={form.quantity} onChange={(event) => setForm({ ...form, quantity: event.target.value })} /></label><label>平均成本<input type="number" min="0.000001" step="any" value={form.average_cost} onChange={(event) => setForm({ ...form, average_cost: event.target.value })} /></label></div><p className="position-cost-preview">成本金额：<strong>{enteredCostAmount ?? "请填写有效的持有股数和平均成本"}</strong></p><label>备注<textarea value={form.notes} onChange={(event) => setForm({ ...form, notes: event.target.value })} /></label><button className="primary">保存模拟持仓</button></form></section><section className="panel"><div className="panel-head"><div><h2>模拟组合概览</h2><p>{positions.length} 个手动录入持仓；不含佣金、税费、分红、现金余额或汇率换算。</p></div><button className="primary" onClick={() => void refreshOverview()} disabled={refreshing}>{refreshing ? "正在更新…" : "刷新组合估值"}</button></div><PortfolioSummary overview={overview} /></section></section><section className="panel paper-position-panel"><div className="panel-head"><div><p className="eyebrow">PAPER POSITIONS</p><h2>模拟持仓明细</h2><p>当日盈亏采用上一收盘价；本月盈亏按当前数量与月初前一交易日收盘价估算。</p></div>{overview && <small className="brief-time">更新于 {new Date(overview.observed_at).toLocaleString()}</small>}</div>{overview?.notices.map((notice) => <div className="notice" key={notice}>{notice}</div>)}<div className="position-list">{positions.map((item) => { const valuation = overview?.valuations.find((entry) => entry.position_id === item.position_id); return <article className="position-item" key={item.position_id}><div><strong>{item.display_name || item.symbol}</strong><p>{item.symbol} · {currencyForPosition(item, valuation)}</p><PositionHoldingMetrics position={item} valuation={valuation} />{valuation ? <><small>现价 {valuation.last_price} {valuation.currency} · 市值 {formatPortfolioMoney(valuation.market_value, valuation.currency)}</small><div className="position-performance"><span className={profitTone(valuation.daily_pnl)}>当日 {formatPortfolioChange(valuation.daily_pnl, valuation.currency, valuation.daily_pnl_percent)}</span><span className={profitTone(valuation.month_to_date_pnl)}>本月 {formatPortfolioChange(valuation.month_to_date_pnl, valuation.currency, valuation.month_to_date_pnl_percent)}</span></div></> : <small>正在读取行情或该持仓暂不能估值</small>}</div><button className="secondary" onClick={() => void remove(item.position_id)}>删除</button></article>; })}</div></section></section>;
}

function AiSimulationWorkspace({ strategies }: { strategies: Strategy[] }) {
  const [market, setMarket] = useState<Exclude<Market, "fund">>("a_share");
  const [initialCapital, setInitialCapital] = useState("100000");
  const [maxPositions, setMaxPositions] = useState(3);
  const [strategyId, setStrategyId] = useState("");
  const [overview, setOverview] = useState<AiSimulationOverview | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const availableStrategies = strategies.filter((item) => item.status === "active" && item.markets.includes(market));
  useEffect(() => { let active = true; setOverview(null); setMessage(null); void fetchAiSimulationOverview(market).then((result) => { if (active) setOverview(result); }).catch(() => undefined); return () => { active = false; }; }, [market]);
  async function run() { setRunning(true); setMessage(null); try { const result = await runAiSimulation({ market, initial_capital: initialCapital, max_positions: maxPositions, strategy_id: strategyId || null }); setOverview(result); setMessage(result.positions.length ? "AI 已完成本轮模拟筛选与风险预算分配。" : "本轮没有候选满足全部模拟建仓条件，未创建交易。"); } catch (error) { setMessage(error instanceof Error ? error.message : "AI 模拟选股失败"); } finally { setRunning(false); } }
  return <section className="ai-simulation-workspace"><section className="panel"><div className="panel-head"><div><p className="eyebrow">AUDITABLE AI PAPER TRADING</p><h2>AI 模拟选股与交易</h2><p>基于预设高流动性候选样本、实际可用的内置因子、启用策略的仓位上限，以及趋势跟随、分散化和风险预算规则自动决定是否创建模拟买入。</p></div></div><div className="ai-simulation-controls"><label>市场<select value={market} onChange={(event) => setMarket(event.target.value as Exclude<Market, "fund">)}><option value="a_share">A 股</option><option value="hong_kong">港股</option><option value="united_states">美股</option></select></label><label>初始本金<input type="number" min="1" step="any" value={initialCapital} onChange={(event) => setInitialCapital(event.target.value)} /></label><label>最多持仓<select value={maxPositions} onChange={(event) => setMaxPositions(Number(event.target.value))}>{[1, 2, 3, 4, 5].map((value) => <option value={value} key={value}>{value} 只</option>)}</select></label><label>注入策略<select value={strategyId} onChange={(event) => setStrategyId(event.target.value)}><option value="">使用内置风险预算</option>{availableStrategies.map((strategy) => <option key={strategy.strategy_id} value={strategy.strategy_id}>{strategy.name}（上限 {strategy.max_position_pct}%）</option>)}</select></label></div><div className="ai-simulation-actions"><button className="primary" onClick={() => void run()} disabled={running}>{running ? "AI 正在筛选与估值…" : "执行一轮 AI 模拟"}</button><small>仅记录本地模拟交易。因子数据缺失、候选分数不足或风险预算不足时，AI 会保持现金而不会模拟买入。</small></div>{message && <p className="ai-simulation-message">{message}</p>}</section>{overview ? <AiSimulationOverviewView overview={overview} /> : <section className="panel ai-simulation-empty"><h3>尚未建立 {market === "a_share" ? "A 股" : market === "hong_kong" ? "港股" : "美股"} AI 模拟组合</h3><p>设置本金与最多持仓数后，执行一轮 AI 模拟。创建后会独立记录现金、持仓成本和逐次模拟交易，不会影响手动模拟持仓。</p></section>}</section>;
}

function AiSimulationOverviewView({ overview }: { overview: AiSimulationOverview }) {
  const currency = overview.currency;
  return <section className="ai-simulation-results"><section className="panel"><div className="panel-head"><div><h2>AI 模拟账户</h2><p>已运行的模拟组合；现金余额与持仓市值共同构成总权益。</p></div><small className="brief-time">更新于 {new Date(overview.observed_at).toLocaleString()}</small></div><div className="portfolio-metrics ai-portfolio-metrics"><PortfolioMetric label="初始本金" value={formatPortfolioMoney(overview.initial_capital, currency)} /><PortfolioMetric label="可用现金" value={formatPortfolioMoney(overview.cash_balance, currency)} /><PortfolioMetric label="持仓成本" value={formatPortfolioMoney(overview.invested_cost, currency)} /><PortfolioMetric label="总市值" value={formatPortfolioMoney(overview.market_value, currency)} /><PortfolioMetric label="账户总权益" value={formatPortfolioMoney(overview.total_equity, currency)} /><PortfolioMetric label="累计收益" value={formatPortfolioMoney(overview.cumulative_pnl, currency, true)} tone={profitTone(overview.cumulative_pnl)} /><PortfolioMetric label="当日盈亏" value={formatPortfolioMoney(overview.daily_pnl, currency, true)} tone={profitTone(overview.daily_pnl)} /><PortfolioMetric label="本月盈亏" value={formatPortfolioMoney(overview.month_to_date_pnl, currency, true)} tone={profitTone(overview.month_to_date_pnl)} /></div></section><section className="panel paper-position-panel"><div className="panel-head"><div><h2>AI 模拟持仓</h2><p>每笔建仓均保留候选评分、实际参与判断的因子和原因，便于复核。</p></div><small>{overview.positions.length}/{overview.max_positions} 个持仓槽位</small></div>{overview.notices.map((notice) => <div className="notice" key={notice}>{notice}</div>)}{overview.positions.length ? <div className="ai-simulation-position-list">{overview.positions.map((position) => <article className="ai-simulation-position" key={position.position_id}><div className="ai-position-head"><div><strong>{position.symbol}</strong><small>候选评分 {position.candidate_score}/100 · 模拟建仓于 {new Date(position.opened_at).toLocaleString()}</small></div><strong className={profitTone(position.unrealized_pnl)}>{formatPortfolioMoney(position.unrealized_pnl, currency, true)}</strong></div><dl className="position-holding-metrics"><div><dt>持有股数</dt><dd>{formatPositionNumber(position.quantity)}</dd></div><div><dt>平均成本</dt><dd>{formatPositionNumber(position.average_cost)} {currency}</dd></div><div><dt>成本金额</dt><dd>{formatPortfolioMoney(position.cost_amount, currency)}</dd></div><div><dt>现价 / 市值</dt><dd>{position.last_price === null ? "行情不可用" : `${formatPositionNumber(position.last_price)} · ${formatPortfolioMoney(position.market_value, currency)}`}</dd></div><div><dt>累计收益</dt><dd className={profitTone(position.unrealized_pnl)}>{formatPortfolioChange(position.unrealized_pnl, currency, position.unrealized_pnl_percent)}</dd></div><div><dt>当日盈亏</dt><dd className={profitTone(position.daily_pnl)}>{formatPortfolioMoney(position.daily_pnl, currency, true)}</dd></div><div><dt>本月盈亏</dt><dd className={profitTone(position.month_to_date_pnl)}>{formatPortfolioMoney(position.month_to_date_pnl, currency, true)}</dd></div></dl><div className="ai-factor-context">{position.factor_context.map((factor) => <span className="tag info" key={factor}>{factor}</span>)}</div><ul className="ai-simulation-rationale">{position.rationale.map((reason) => <li key={reason}>{reason}</li>)}</ul></article>)}</div> : <p className="muted portfolio-empty">当前没有持仓。AI 会在候选评分、可用因子和风险预算同时满足时才创建模拟买入。</p>}</section></section>;
}

function PositionHoldingMetrics({ position, valuation }: { position: PaperPosition; valuation?: PaperPositionValuation }) {
  const currency = currencyForPosition(position, valuation);
  return <dl className="position-holding-metrics"><div><dt>持有股数</dt><dd>{formatPositionNumber(position.quantity)}</dd></div><div><dt>平均成本</dt><dd>{formatPositionNumber(position.average_cost)} {currency}</dd></div><div><dt>成本金额</dt><dd>{formatPortfolioMoney(position.cost_amount, currency)}</dd></div><div><dt>累计盈亏</dt><dd className={profitTone(valuation?.unrealized_pnl ?? null)}>{valuation ? `${formatPortfolioMoney(valuation.unrealized_pnl, currency, true)} · ${formatPercentValue(valuation.unrealized_pnl_percent)}` : "行情不可用"}</dd></div></dl>;
}

function PortfolioSummary({ overview }: { overview: PaperPortfolioOverview | null }) {
  if (!overview) return <p className="muted portfolio-empty">正在读取组合行情与月度参考价格…</p>;
  if (overview.currencies.length === 0) return <p className="muted portfolio-empty">尚未录入模拟持仓。录入后将按币种展示投入本金、总市值与盈亏。</p>;
  return <div className="portfolio-summary-list">{overview.currencies.map((summary) => <section className="portfolio-currency-summary" key={summary.currency}><div className="portfolio-summary-head"><h3>{summary.currency} 模拟账户</h3><small>{summary.position_count} 个已估值持仓</small></div><div className="portfolio-metrics"><PortfolioMetric label="投入本金" value={formatPortfolioMoney(summary.initial_principal, summary.currency)} note="数量 × 平均成本" /><PortfolioMetric label="总市值" value={formatPortfolioMoney(summary.total_market_value, summary.currency)} /><PortfolioMetric label="累计收益" value={formatPortfolioMoney(summary.cumulative_pnl, summary.currency, true)} detail={formatPercentValue(summary.cumulative_return_percent)} tone={profitTone(summary.cumulative_pnl)} /><PortfolioMetric label="当日盈亏" value={formatPortfolioMoney(summary.daily_pnl, summary.currency, true)} detail={formatPercentValue(summary.daily_return_percent)} tone={profitTone(summary.daily_pnl)} /><PortfolioMetric label="本月盈亏" value={formatPortfolioMoney(summary.month_to_date_pnl, summary.currency, true)} detail={formatPercentValue(summary.month_to_date_return_percent)} tone={profitTone(summary.month_to_date_pnl)} /></div>{(summary.daily_pnl === null || summary.month_to_date_pnl === null) && <p className="portfolio-summary-note">部分参考价不可用：当日覆盖 {summary.daily_coverage_count}/{summary.position_count}，本月覆盖 {summary.month_coverage_count}/{summary.position_count}。</p>}</section>)}</div>;
}

function PortfolioMetric({ label, value, detail, note, tone }: { label: string; value: string; detail?: string; note?: string; tone?: string }) { return <article className="portfolio-metric"><small>{label}</small><strong className={tone}>{value}</strong>{detail && <span className={tone}>{detail}</span>}{note && <span>{note}</span>}</article>; }

function formatPortfolioMoney(value: string | null, currency: string, signed = false) { if (value === null) return "—"; const number = Number(value); if (!Number.isFinite(number)) return value; const prefix = signed && number > 0 ? "+" : ""; return `${prefix}${new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 2 }).format(number)} ${currency}`; }
function formatPositionNumber(value: string) { const number = Number(value); return Number.isFinite(number) ? new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 4 }).format(number) : value; }
function calculatePositionCost(quantity: string, averageCost: string) { const result = Number(quantity) * Number(averageCost); return Number.isFinite(result) && result > 0 ? new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 2 }).format(result) : null; }
function currencyForPosition(position: PaperPosition, valuation?: PaperPositionValuation) { if (valuation) return valuation.currency; if (position.market === "hong_kong") return "HKD"; if (position.market === "united_states") return "USD"; return "CNY"; }
function formatPercentValue(value: string | null) { if (value === null) return "参考价不可用"; const number = Number(value); return Number.isFinite(number) ? `${number > 0 ? "+" : ""}${number.toFixed(2)}%` : value; }
function profitTone(value: string | null) { return value !== null && Number(value) < 0 ? "profit down" : value !== null && Number(value) > 0 ? "profit up" : ""; }
function formatPortfolioChange(value: string | null, currency: string, percent: string | null) { return `${formatPortfolioMoney(value, currency, true)} · ${formatPercentValue(percent)}`; }

function FundWorkspace() {
  const [symbol, setSymbol] = useState("510300.SH"); const [market, setMarket] = useState<Market>("a_share"); const [instrumentType, setInstrumentType] = useState<InstrumentType>("etf");
  const [report, setReport] = useState<FundResearch | null>(null); const [error, setError] = useState<string | null>(null); const [loading, setLoading] = useState(false);
  async function submit(event: FormEvent) { event.preventDefault(); setLoading(true); setError(null); try { setReport(await fetchFundResearch(symbol, market, instrumentType)); } catch (reason) { setError(reason instanceof Error ? reason.message : "基金研究请求失败"); } finally { setLoading(false); } }
  const fund = report?.fund;
  return <section className="panel"><div className="panel-head"><div><h2>基金与 ETF 深度研究</h2><p>ETF 使用场内行情和日 K；场外基金使用净值和定期披露，不会伪造成实时成交数据。</p></div></div><form onSubmit={submit}><TickerFields symbol={symbol} market={market} instrumentType={instrumentType} setSymbol={setSymbol} setMarket={setMarket} /><InstrumentTypeField value={instrumentType} setValue={setInstrumentType} /><button className="primary" disabled={loading}>{loading ? "读取基金数据…" : "分析基金 / ETF"}</button></form>{error && <div className="notice">{error}</div>}{fund && <div className="research-results"><DataCard title="基金概览与最新净值" data={fund.overview as Record<string, unknown>} /><DataCard title="区间收益与回撤（%）" data={{ returns_percent: fund.returns_percent, drawdowns_percent: fund.drawdowns_percent }} /><DataCard title="重仓持仓与资产配置（披露口径）" data={{ holdings: fund.holdings, asset_allocations: fund.asset_allocations, institutional_holding_percent: fund.institutional_holding_percent }} /><DataCard title="基金诊断与资讯" data={{ diagnostics: fund.diagnostics, news: fund.news, limitations: fund.limitations }} /></div>}</section>;
}

function TechnicalStudyView({ study }: { study: TechnicalStudy }) {
  const indicators = study.indicators; const profile = study.volume_profile;
  const maxVolume = Math.max(...profile.levels.map((level) => Number(level.volume)), 1);
  const periodLabel = study.timeframe === "1d" ? "日 K" : study.timeframe === "1w" ? "周 K" : "月 K";
  return <div className="technical-results"><div className="panel-head"><div><p className="eyebrow">FOCUSED INSTRUMENT STUDY</p><h2>{study.symbol} · {periodLabel}</h2><p>来源：{study.source}。A 股/ETF 使用真实日线后按周或月聚合；不执行全市场扫描。</p></div><span className="pill">{study.currency}</span></div><div className="metric-grid"><Metric label="趋势" value={study.assessment.trend} /><Metric label="动量" value={study.assessment.momentum} /><Metric label="量能压力" value={study.assessment.volume_pressure} /><Metric label="RSI(14)" value={String(indicators.rsi_14 ?? "—")} /></div><section className="chart-box"><div className="panel-head"><div><h3>{periodLabel}与均线</h3><p className="muted">蜡烛为 OHLC，底部柱体为成交量；均线基于当前所选周期的收盘价计算。</p></div><div className="ma-legend"><span className="ma5">MA5</span><span className="ma10">MA10</span><span className="ma20">MA20</span><span className="ma60">MA60</span></div></div><CandlestickChart bars={study.bars} /><div className="indicator-row">最新 MA5 {indicators.sma_5 ?? "—"} · MA10 {indicators.sma_10 ?? "—"} · MA20 {indicators.sma_20 ?? "—"} · MA60 {indicators.sma_60 ?? "—"} · MACD {indicators.macd ?? "—"} · ATR {indicators.atr_14 ?? "—"}</div></section><section className="profile-box"><div><h3>Volume Profile 水平成交量分布</h3><p>POC {profile.point_of_control ?? "—"} · 70% 价值区 {profile.value_area_low ?? "—"} — {profile.value_area_high ?? "—"}</p></div><div className="profile-levels">{profile.levels.slice().reverse().map((level) => <div className="profile-level" key={String(level.price)}><span>{level.price}</span><i style={{ width: `${Math.max(2, Number(level.volume) / maxVolume * 100)}%` }} /><b>{level.percent}%</b></div>)}</div></section><section className="analysis-box"><h3>规则化解读</h3><ul>{study.assessment.observations.map((item) => <li key={item}>{item}</li>)}</ul><p>自选标的的 AI 解读会结合行情、资讯、基本面与个人策略补充研究依据。</p>{study.assessment.limitations.map((item) => <small key={item}>{item}</small>)}</section></div>;
}

function CandlestickChart({ bars }: { bars: TechnicalStudy["bars"] }) {
  const series = bars.slice(-80).map((bar) => ({
    ...bar, open: Number(bar.open), high: Number(bar.high), low: Number(bar.low), close: Number(bar.close), volume: Number(bar.volume)
  })).filter((bar) => [bar.open, bar.high, bar.low, bar.close, bar.volume].every(Number.isFinite));
  if (series.length < 2) return <p className="muted">可用 K 线不足，暂不能绘制图表。</p>;
  const width = 1000; const priceTop = 14; const priceHeight = 225; const volumeTop = 258; const volumeHeight = 68; const left = 44; const right = 16;
  const prices = series.flatMap((bar) => [bar.high, bar.low]); const minPrice = Math.min(...prices); const maxPrice = Math.max(...prices); const priceRange = Math.max(maxPrice - minPrice, Math.abs(maxPrice) * 0.02, 0.01);
  const maxVolume = Math.max(...series.map((bar) => bar.volume), 1); const step = (width - left - right) / series.length; const bodyWidth = Math.max(2, Math.min(9, step * 0.62));
  const y = (price: number) => priceTop + (maxPrice - price) / priceRange * priceHeight; const x = (index: number) => left + (index + .5) * step;
  const movingAverage = (period: number) => series.map((bar, index) => {
    if (index < period - 1) return null; const closes = series.slice(index - period + 1, index + 1).map((item) => item.close); return { x: x(index), y: y(closes.reduce((sum, value) => sum + value, 0) / period) };
  }).filter((point): point is { x: number; y: number } => point !== null);
  const linePoints = (period: number) => movingAverage(period).map((point) => `${point.x},${point.y}`).join(" ");
  return <svg className="candlestick-chart" viewBox="0 0 1000 350" role="img" aria-label="K 线、成交量和移动平均线"><line x1={left} y1={priceTop + priceHeight} x2={width - right} y2={priceTop + priceHeight} className="chart-axis" /><line x1={left} y1={volumeTop + volumeHeight} x2={width - right} y2={volumeTop + volumeHeight} className="chart-axis" /><text x="4" y={priceTop + 9} className="chart-label">{maxPrice.toFixed(2)}</text><text x="4" y={priceTop + priceHeight} className="chart-label">{minPrice.toFixed(2)}</text>{series.map((bar, index) => { const up = bar.close >= bar.open; const color = up ? "#d94b4b" : "#1a9b68"; const highY = y(bar.high); const lowY = y(bar.low); const openY = y(bar.open); const closeY = y(bar.close); const candleTop = Math.min(openY, closeY); return <g key={bar.date}><line x1={x(index)} y1={highY} x2={x(index)} y2={lowY} stroke={color} strokeWidth="1.3" /><rect x={x(index) - bodyWidth / 2} y={candleTop} width={bodyWidth} height={Math.max(1.5, Math.abs(openY - closeY))} fill={color} opacity=".92"><title>{`${bar.date} 开 ${bar.open} 高 ${bar.high} 低 ${bar.low} 收 ${bar.close} 成交量 ${bar.volume}`}</title></rect><rect x={x(index) - bodyWidth / 2} y={volumeTop + volumeHeight - bar.volume / maxVolume * volumeHeight} width={bodyWidth} height={Math.max(1, bar.volume / maxVolume * volumeHeight)} fill={color} opacity=".45" /></g>; })}<polyline points={linePoints(5)} className="ma-line ma5-line" /><polyline points={linePoints(10)} className="ma-line ma10-line" /><polyline points={linePoints(20)} className="ma-line ma20-line" /><polyline points={linePoints(60)} className="ma-line ma60-line" /><text x={left} y="345" className="chart-label">{series[0].date}</text><text x={width - right - 70} y="345" className="chart-label">{series[series.length - 1].date}</text></svg>;
}

function StrategyWorkspace({ factors, strategies, error, reload }: { factors: Factor[]; strategies: Strategy[]; error: string | null; reload: () => void }) {
  const [selectedId, setSelectedId] = useState(""); const [form, setForm] = useState<StrategyInput>(defaultStrategy); const [message, setMessage] = useState<string | null>(null);
  function select(id: string) { setSelectedId(id); const found = strategies.find((item) => item.strategy_id === id); if (found) { const { strategy_id, version, ...input } = found; setForm(input); } }
  function toggleFactor(identifier: string) { setForm((current) => ({ ...current, factor_ids: current.factor_ids.includes(identifier) ? current.factor_ids.filter((item) => item !== identifier) : [...current.factor_ids, identifier] })); }
  function toggleMarket(market: Market) { setForm((current) => ({ ...current, markets: current.markets.includes(market) ? current.markets.filter((item) => item !== market) : [...current.markets, market] })); }
  async function submit(event: FormEvent) { event.preventDefault(); setMessage(null); try { if (selectedId) await updateStrategy(selectedId, form); else { const saved = await createStrategy(form); setSelectedId(saved.strategy_id); } reload(); setMessage("策略已保存，可在首页选择“注入策略”供 AI 研究使用。"); } catch (reason) { setMessage(reason instanceof Error ? reason.message : "策略保存失败"); } }
  return <section className="strategy-layout"><aside className="strategy-list"><button className="secondary" onClick={() => { setSelectedId(""); setForm(defaultStrategy); }}>新建策略</button>{strategies.map((item) => <button key={item.strategy_id} className={selectedId === item.strategy_id ? "strategy-choice selected" : "strategy-choice"} onClick={() => select(item.strategy_id)}><strong>{item.name}</strong><small>{item.status} · v{item.version}</small></button>)}</aside><section className="panel"><h2>{selectedId ? "编辑个人策略" : "新建个人策略"}</h2><p>策略是声明式研究偏好，不执行任意代码；保存后可被 AI 对话显式注入。</p>{error && <div className="notice">{error}</div>}{message && <div className="success">{message}</div>}<form onSubmit={submit}><label>名称<input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} /></label><label>研究逻辑 / 交易假设<textarea value={form.thesis} onChange={(event) => setForm({ ...form, thesis: event.target.value })} /></label><fieldset><legend>可选因子</legend>{factors.map((factor) => <label className="check" key={factor.identifier}><input type="checkbox" checked={form.factor_ids.includes(factor.identifier)} onChange={() => toggleFactor(factor.identifier)} />{factor.name}</label>)}</fieldset><fieldset><legend>市场</legend>{(["a_share", "hong_kong", "united_states", "fund"] as Market[]).map((item) => <label className="check" key={item}><input type="checkbox" checked={form.markets.includes(item)} onChange={() => toggleMarket(item)} />{item}</label>)}</fieldset><div className="form-row"><label>单标的上限 %<input type="number" min="0.1" max="100" step="0.1" value={form.max_position_pct} onChange={(event) => setForm({ ...form, max_position_pct: event.target.value })} /></label><label>状态<select value={form.status} onChange={(event) => setForm({ ...form, status: event.target.value as StrategyInput["status"] })}><option value="draft">draft</option><option value="active">active</option><option value="archived">archived</option></select></label></div><label>风险约束<textarea value={form.risk_notes} onChange={(event) => setForm({ ...form, risk_notes: event.target.value })} /></label><button className="primary">保存并生成新版本</button></form></section></section>;
}

function DisciplineWorkspace({ disciplines, error, reload }: { disciplines: Discipline[]; error: string | null; reload: () => void }) {
  const [selectedId, setSelectedId] = useState(""); const [form, setForm] = useState<DisciplineInput>(defaultDiscipline); const [message, setMessage] = useState<string | null>(null);
  function select(id: string) { setSelectedId(id); const found = disciplines.find((item) => item.discipline_id === id); if (found) { const { discipline_id, version, ...input } = found; setForm(input); } }
  async function submit(event: FormEvent) { event.preventDefault(); setMessage(null); try { if (selectedId) await updateDiscipline(selectedId, form); else { const saved = await createDiscipline(form); setSelectedId(saved.discipline_id); } reload(); setMessage("个人纪律已保存。它仅用于提醒与复核，不会自动发出交易指令。"); } catch (reason) { setMessage(reason instanceof Error ? reason.message : "个人纪律保存失败"); } }
  return <section className="discipline-layout"><aside className="strategy-list"><button className="secondary" onClick={() => { setSelectedId(""); setForm(defaultDiscipline); }}>新建纪律</button>{disciplines.map((item) => <button key={item.discipline_id} className={selectedId === item.discipline_id ? "strategy-choice selected" : "strategy-choice"} onClick={() => select(item.discipline_id)}><strong>{item.name}</strong><small>{item.symbol} · {item.status} · v{item.version}</small></button>)}</aside><section className="panel"><h2>{selectedId ? "编辑个人纪律" : "新建个人纪律"}</h2><p>设定目标价位后，仍须由你自行复核并手动执行。系统不会自动下单。</p>{error && <div className="notice">{error}</div>}{message && <div className="success">{message}</div>}<form onSubmit={submit}><label>纪律名称<input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} /></label><TickerFields symbol={form.symbol} market={form.market} setSymbol={(symbol) => setForm({ ...form, symbol })} setMarket={(market) => setForm({ ...form, market })} /><div className="discipline-prices"><label>买入价<input type="number" min="0.0001" step="0.0001" value={form.buy_price} onChange={(event) => setForm({ ...form, buy_price: event.target.value })} /></label><label>加仓价（可选）<input type="number" min="0.0001" step="0.0001" value={form.add_price ?? ""} onChange={(event) => setForm({ ...form, add_price: event.target.value || null })} /></label><label>止盈价<input type="number" min="0.0001" step="0.0001" value={form.take_profit_price} onChange={(event) => setForm({ ...form, take_profit_price: event.target.value })} /></label><label>清仓价<input type="number" min="0.0001" step="0.0001" value={form.exit_price} onChange={(event) => setForm({ ...form, exit_price: event.target.value })} /></label></div><p className="muted">有效顺序：清仓价 &lt; 买入价 &lt; 加仓价 &lt; 止盈价。加仓价可以留空。</p><label>复核备注<textarea value={form.notes} onChange={(event) => setForm({ ...form, notes: event.target.value })} /></label><label>状态<select value={form.status} onChange={(event) => setForm({ ...form, status: event.target.value as DisciplineInput["status"] })}><option value="active">active（启用）</option><option value="paused">paused（暂停）</option><option value="archived">archived（归档）</option></select></label><button className="primary">保存纪律</button></form></section></section>;
}

function Metric({ label, value }: { label: string; value: string }) { return <article className="card"><p className="muted">{label}</p><h3>{value}</h3></article>; }
function DataCard({ title, data }: { title: string; data: Record<string, unknown> | null }) { return <article className="data-card"><h3>{title}</h3>{data ? <pre>{JSON.stringify(data, null, 2)}</pre> : <p className="muted">暂无可用数据</p>}</article>; }
function FutureWorkspace({ page }: { page: string }) { return <section className="panel empty"><p className="eyebrow">NEXT MODULE</p><h2>{page}</h2><p>数据库结构和独立页面边界已准备；下一步接入文件上传/OCR 或交易日志导入用例。</p></section>; }

export default App;
