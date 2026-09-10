import { FormEvent, useEffect, useState } from "react";
import {
  askAssistant, createDiscipline, createStrategy, Discipline, DisciplineDecision, DisciplineInput, fetchDisciplines,
  fetchFactors, fetchNews, fetchQuote, fetchResearch, fetchStrategies, Factor, Market, NewsItem,
  ResearchReport, Strategy, StrategyInput, updateDiscipline, InstrumentType, FundResearch, fetchFundResearch,
  updateStrategy, fetchTechnicalStudy, TechnicalStudy, WatchlistInput, WatchlistItem,
  createWatchlistItem, deleteWatchlistItem, fetchWatchlist, PaperPositionInput, PaperPosition,
  createPaperPosition, deletePaperPosition, fetchPaperPositions, fetchPaperValuations, PaperPositionValuation,
  fetchWatchlistAnalyses, fetchWatchlistAnalysis, refreshWatchlistAnalysis, WatchlistAnalysis, Quote
} from "./api";

type Page = "dashboard" | "watchlist" | "positions" | "funds" | "news" | "research" | "strategies" | "disciplines" | "documents" | "journal" | "settings";

const navigation: Array<{ id: Page; label: string; description: string }> = [
  { id: "dashboard", label: "总览", description: "AI 研究对话与自选标的" },
  { id: "watchlist", label: "自选跟踪", description: "标签化解读与单标的深度研究" },
  { id: "positions", label: "模拟持仓", description: "手动成本、数量与未实现盈亏" },
  { id: "funds", label: "基金 / ETF", description: "净值、收益、持仓、回撤与基金资讯" },
  { id: "news", label: "财经资讯", description: "公开资讯与情绪" },
  { id: "research", label: "研究分析", description: "基本面、情绪、资金流、期权" },
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
      {page === "dashboard" && <Dashboard strategies={strategies} />}
      {page === "watchlist" && <WatchlistWorkspace />}
      {page === "positions" && <PaperPortfolioWorkspace />}
      {page === "funds" && <FundWorkspace />}
      {page === "news" && <NewsWorkspace />}
      {page === "research" && <ResearchWorkspace />}
      {page === "strategies" && <StrategyWorkspace factors={factors} strategies={strategies} error={strategyError} reload={reloadStrategies} />}
      {page === "disciplines" && <DisciplineWorkspace disciplines={disciplines} error={disciplineError} reload={reloadDisciplines} />}
      {["documents", "journal", "settings"].includes(page) && <FutureWorkspace page={active.label} />}
    </section>
  </main>;
}

function TickerFields({ symbol, market, setSymbol, setMarket }: { symbol: string; market: Market; setSymbol: (value: string) => void; setMarket: (value: Market) => void }) {
  return <div className="form-row"><label>代码<input value={symbol} onChange={(event) => setSymbol(event.target.value)} placeholder="股票填 600519；ETF 填 510300.SH；基金填 025480.OF" /></label><label>市场<select value={market} onChange={(event) => setMarket(event.target.value as Market)}><option value="a_share">A 股</option><option value="hong_kong">港股</option><option value="united_states">美股</option><option value="fund">场外基金</option></select></label></div>;
}

function InstrumentTypeField({ value, setValue }: { value: InstrumentType; setValue: (value: InstrumentType) => void }) {
  return <label>类别<select value={value} onChange={(event) => setValue(event.target.value as InstrumentType)}><option value="equity">股票</option><option value="etf">ETF（场内）</option><option value="fund">公募基金（场外）</option></select></label>;
}

function Dashboard({ strategies }: { strategies: Strategy[] }) {
  const [question, setQuestion] = useState("请结合今日行情、财经资讯和我的策略分析这个标的。");
  const [symbol, setSymbol] = useState("600519.SH");
  const [market, setMarket] = useState<Market>("a_share");
  const [instrumentType, setInstrumentType] = useState<InstrumentType>("equity");
  const [strategyId, setStrategyId] = useState("");
  const [answer, setAnswer] = useState<string | null>(null);
  const [status, setStatus] = useState<string[]>([]);
  const [decisions, setDecisions] = useState<DisciplineDecision[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault(); setLoading(true); setError(null); setAnswer(null); setDecisions([]);
    try { const result = await askAssistant({ question, symbol, market, instrument_type: instrumentType, strategy_id: strategyId || undefined }); setAnswer(result.answer); setStatus(result.context_status); setDecisions(result.discipline_decisions ?? []); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "AI 请求失败"); }
    finally { setLoading(false); }
  }
  return <><section className="hero"><div><p className="eyebrow">SOURCE-GROUNDED AI</p><h2>问问今天的市场</h2><p>个人纪律状态由后端价位规则计算；AI 仅结合行情、资讯、研究和已选策略解释依据。浏览器不会接触任何密钥。</p></div></section>
    <section className="panel chat-panel"><form onSubmit={submit}><TickerFields symbol={symbol} market={market} setSymbol={setSymbol} setMarket={setMarket} /><InstrumentTypeField value={instrumentType} setValue={setInstrumentType} /><label>注入策略<select value={strategyId} onChange={(event) => setStrategyId(event.target.value)}><option value="">不注入个人策略</option>{strategies.filter((item) => item.status === "active").map((item) => <option key={item.strategy_id} value={item.strategy_id}>{item.name} v{item.version}</option>)}</select></label><label>你的问题<textarea value={question} onChange={(event) => setQuestion(event.target.value)} /></label><button className="primary" disabled={loading}>{loading ? "正在汇总研究…" : "获取 AI 解读与纪律状态"}</button></form>{error && <div className="notice">{error}</div>}{answer && <article className="answer">{decisions.length > 0 && <section className="decision-list"><p className="eyebrow">PERSONAL DISCIPLINE STATUS</p>{decisions.map((decision) => <article className={`decision-card ${decision.status}`} key={decision.discipline_id}><div><strong>{decision.label}</strong><p>{decision.discipline_name} · 现价 {decision.last_price}</p></div><small>{decision.rationale}</small></article>)}</section>}<p className="eyebrow">AI RESEARCH RESPONSE</p><p>{answer}</p><div className="status-list">{status.map((item) => <span key={item}>{item}</span>)}</div><small>纪律状态仅供你手动复核；研究结果不构成投资或交易指令，系统不会自动下单。</small></article>}</section></>;
}

const defaultWatchlist: WatchlistInput = { symbol: "600519.SH", market: "a_share", instrument_type: "equity", label: "", notes: "" };
const defaultPaperPosition: PaperPositionInput = { symbol: "600519.SH", market: "a_share", instrument_type: "equity", quantity: "100", average_cost: "100", notes: "仅用于模拟，不连接券商。" };

function WatchlistWorkspace() {
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [analyses, setAnalyses] = useState<WatchlistAnalysis[]>([]);
  const [form, setForm] = useState(defaultWatchlist);
  const [message, setMessage] = useState<string | null>(null);
  const [selected, setSelected] = useState<WatchlistItem | null>(null);
  const [quote, setQuote] = useState<Quote | null>(null);
  const [report, setReport] = useState<ResearchReport | null>(null);
  const [study, setStudy] = useState<TechnicalStudy | null>(null);
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
        setSelected(null); setQuote(null); setReport(null); setStudy(null);
      }
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "删除失败");
    }
  }

  async function selectItem(item: WatchlistItem) {
    setSelected(item); setQuote(null); setReport(null); setStudy(null); setDetailLoading(true); setMessage(null);
    const [quoteResult, researchResult, studyResult, analysisResult] = await Promise.allSettled([
      fetchQuote(item.symbol, item.market, item.instrument_type),
      fetchResearch(item.symbol, item.market, item.instrument_type),
      fetchTechnicalStudy(item.symbol, item.market, "1d", item.instrument_type),
      fetchWatchlistAnalysis(item.item_id)
    ]);
    if (quoteResult.status === "fulfilled") setQuote(quoteResult.value);
    if (researchResult.status === "fulfilled") setReport(researchResult.value);
    if (studyResult.status === "fulfilled") setStudy(studyResult.value);
    if (analysisResult.status === "fulfilled") upsertAnalysis(analysisResult.value);
    const failures = [quoteResult, researchResult, studyResult].filter((result) => result.status === "rejected");
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

  const selectedAnalysis = selected
    ? analyses.find((item) => item.watchlist_item_id === selected.item_id) ?? null
    : null;
  return <section className="watchlist-workspace">
    <section className="portfolio-layout">
      <section className="panel"><h2>添加自选标的</h2><p>只保存你明确选择的股票、ETF 或基金；不会启动全市场扫描。</p>{message && <div className="success">{message}</div>}<form onSubmit={save}><TickerFields symbol={form.symbol} market={form.market} setSymbol={(symbol) => setForm({ ...form, symbol })} setMarket={(market) => setForm({ ...form, market })} /><InstrumentTypeField value={form.instrument_type} setValue={(instrument_type) => setForm({ ...form, instrument_type })} /><label>显示名称（可选）<input value={form.label} onChange={(event) => setForm({ ...form, label: event.target.value })} /></label><label>跟踪备注<textarea value={form.notes} onChange={(event) => setForm({ ...form, notes: event.target.value })} /></label><button className="primary">加入自选</button></form></section>
      <section className="panel"><div className="panel-head"><div><h2>我的自选</h2><p>点击标的展开当日成交、K 线、资金、情绪与 AI 解读。</p></div><button className="secondary" onClick={() => void load()}>刷新列表</button></div><div className="watchlist-cards">{items.map((item) => { const analysis = analyses.find((entry) => entry.watchlist_item_id === item.item_id); return <article className={selected?.item_id === item.item_id ? "watch-item selected" : "watch-item"} key={item.item_id}><button className="watch-item-main" onClick={() => void selectItem(item)}><strong>{item.label || item.symbol}</strong><p>{item.symbol} · {item.market} · {item.instrument_type}</p><div className="tag-list">{analysis ? analysis.tags.map((tag) => <span className={`tag ${tag.tone}`} key={tag.category}>{tag.label}</span>) : <span className="tag neutral">等待定时分析</span>}</div>{analysis && <small>更新于 {new Date(analysis.observed_at).toLocaleString()} · {analysis.status}</small>}{item.notes && <small>{item.notes}</small>}</button><div className="watch-item-actions"><button className="secondary" onClick={() => void refreshAnalysis(item)} disabled={refreshing}>{refreshing ? "分析中…" : "更新解读"}</button><button className="secondary" onClick={() => void remove(item.item_id)}>移除</button></div></article>; })}</div></section>
    </section>
    {selected && <WatchlistDetail item={selected} quote={quote} report={report} study={study} analysis={selectedAnalysis} loading={detailLoading} onRefresh={() => void refreshAnalysis(selected)} refreshing={refreshing} />}
  </section>;
}

function WatchlistDetail({ item, quote, report, study, analysis, loading, onRefresh, refreshing }: { item: WatchlistItem; quote: Quote | null; report: ResearchReport | null; study: TechnicalStudy | null; analysis: WatchlistAnalysis | null; loading: boolean; onRefresh: () => void; refreshing: boolean }) {
  return <section className="panel watchlist-detail"><div className="panel-head"><div><p className="eyebrow">FOCUSED WATCHLIST STUDY</p><h2>{item.label || item.symbol}</h2><p>仅拉取此自选标的的数据；所有交易决策仍须由你手动复核。</p></div><button className="primary" onClick={onRefresh} disabled={refreshing}>{refreshing ? "正在生成摘要…" : "更新 AI 解读"}</button></div>{loading && <p className="muted">正在读取当日成交和研究数据…</p>}<div className="metric-grid"><Metric label="现价" value={quote ? `${quote.last_price} ${quote.currency}` : "—"} /><Metric label="来源" value={quote?.source ?? "—"} /><Metric label="最新分析" value={analysis ? new Date(analysis.observed_at).toLocaleTimeString() : "等待首次分析"} /><Metric label="状态" value={analysis?.status ?? "—"} /></div>{analysis && <><div className="tag-list detail-tags">{analysis.tags.map((tag) => <span className={`tag ${tag.tone}`} key={tag.category}>{tag.label}</span>)}</div>{analysis.ai_summary && <section className="analysis-box"><h3>AI 研究摘要</h3><p>{analysis.ai_summary}</p></section>}{analysis.notices.map((notice) => <div className="notice" key={notice}>{notice}</div>)}</>}{report && <div className="research-results"><DataCard title="基本面" data={report.fundamentals} /><DataCard title="资金流" data={report.capital_flow} /><DataCard title="新闻情绪" data={report.news_sentiment} /></div>}{study && <TechnicalStudyView study={study} />}</section>;
}

function PaperPortfolioWorkspace() {
  const [positions, setPositions] = useState<PaperPosition[]>([]); const [valuations, setValuations] = useState<PaperPositionValuation[]>([]); const [form, setForm] = useState(defaultPaperPosition); const [message, setMessage] = useState<string | null>(null); const [refreshing, setRefreshing] = useState(false);
  const load = () => fetchPaperPositions().then(setPositions).catch((error: Error) => setMessage(error.message));
  useEffect(() => { load(); }, []);
  async function save(event: FormEvent) { event.preventDefault(); try { await createPaperPosition(form); setForm(defaultPaperPosition); setMessage("模拟持仓已保存；不会产生真实委托。"); load(); } catch (error) { setMessage(error instanceof Error ? error.message : "保存失败"); } }
  async function value() { setRefreshing(true); try { setValuations(await fetchPaperValuations()); } catch (error) { setMessage(error instanceof Error ? error.message : "估值失败"); } finally { setRefreshing(false); } }
  async function remove(positionId: string) { try { await deletePaperPosition(positionId); setValuations((current) => current.filter((item) => item.position_id !== positionId)); load(); } catch (error) { setMessage(error instanceof Error ? error.message : "删除失败"); } }
  return <section className="portfolio-layout"><section className="panel"><h2>录入模拟持仓</h2><p>输入的是你的模拟数量和平均成本；未实现盈亏以主动刷新时的最新行情或净值计算。</p>{message && <div className="success">{message}</div>}<form onSubmit={save}><TickerFields symbol={form.symbol} market={form.market} setSymbol={(symbol) => setForm({ ...form, symbol })} setMarket={(market) => setForm({ ...form, market })} /><InstrumentTypeField value={form.instrument_type} setValue={(instrument_type) => setForm({ ...form, instrument_type })} /><div className="form-row"><label>数量<input type="number" min="0.000001" step="any" value={form.quantity} onChange={(event) => setForm({ ...form, quantity: event.target.value })} /></label><label>平均成本<input type="number" min="0.000001" step="any" value={form.average_cost} onChange={(event) => setForm({ ...form, average_cost: event.target.value })} /></label></div><label>备注<textarea value={form.notes} onChange={(event) => setForm({ ...form, notes: event.target.value })} /></label><button className="primary">保存模拟持仓</button></form></section><section className="panel"><div className="panel-head"><div><h2>模拟盈亏</h2><p>{positions.length} 个手动录入持仓；不含佣金、税费、分红或汇率换算。</p></div><button className="primary" onClick={value} disabled={refreshing}>{refreshing ? "刷新中…" : "刷新模拟估值"}</button></div><div className="position-list">{positions.map((item) => { const valuation = valuations.find((entry) => entry.position_id === item.position_id); return <article className="position-item" key={item.position_id}><div><strong>{item.symbol}</strong><p>数量 {item.quantity} · 成本 {item.average_cost}</p>{valuation ? <small>现价 {valuation.last_price} {valuation.currency} · 市值 {valuation.market_value}</small> : <small>点击“刷新模拟估值”计算行情与盈亏</small>}</div>{valuation && <strong className={Number(valuation.unrealized_pnl) >= 0 ? "profit up" : "profit down"}>{Number(valuation.unrealized_pnl).toFixed(2)}<small> ({Number(valuation.unrealized_pnl_percent).toFixed(2)}%)</small></strong>}<button className="secondary" onClick={() => remove(item.position_id)}>删除</button></article>; })}</div></section></section>;
}

function FundWorkspace() {
  const [symbol, setSymbol] = useState("510300.SH"); const [market, setMarket] = useState<Market>("a_share"); const [instrumentType, setInstrumentType] = useState<InstrumentType>("etf");
  const [report, setReport] = useState<FundResearch | null>(null); const [error, setError] = useState<string | null>(null); const [loading, setLoading] = useState(false);
  async function submit(event: FormEvent) { event.preventDefault(); setLoading(true); setError(null); try { setReport(await fetchFundResearch(symbol, market, instrumentType)); } catch (reason) { setError(reason instanceof Error ? reason.message : "基金研究请求失败"); } finally { setLoading(false); } }
  const fund = report?.fund;
  return <section className="panel"><div className="panel-head"><div><h2>基金与 ETF 深度研究</h2><p>ETF 使用场内行情和日 K；场外基金使用净值和定期披露，不会伪造成实时成交数据。</p></div></div><form onSubmit={submit}><TickerFields symbol={symbol} market={market} setSymbol={setSymbol} setMarket={setMarket} /><InstrumentTypeField value={instrumentType} setValue={setInstrumentType} /><button className="primary" disabled={loading}>{loading ? "读取基金数据…" : "分析基金 / ETF"}</button></form>{error && <div className="notice">{error}</div>}{fund && <div className="research-results"><DataCard title="基金概览与最新净值" data={fund.overview as Record<string, unknown>} /><DataCard title="区间收益与回撤（%）" data={{ returns_percent: fund.returns_percent, drawdowns_percent: fund.drawdowns_percent }} /><DataCard title="重仓持仓与资产配置（披露口径）" data={{ holdings: fund.holdings, asset_allocations: fund.asset_allocations, institutional_holding_percent: fund.institutional_holding_percent }} /><DataCard title="基金诊断与资讯" data={{ diagnostics: fund.diagnostics, news: fund.news, limitations: fund.limitations }} /></div>}</section>;
}

function TechnicalStudyView({ study }: { study: TechnicalStudy }) {
  const indicators = study.indicators; const profile = study.volume_profile;
  const maxVolume = Math.max(...profile.levels.map((level) => Number(level.volume)), 1);
  return <div className="technical-results"><div className="panel-head"><div><p className="eyebrow">FOCUSED INSTRUMENT STUDY</p><h2>{study.symbol} · {study.timeframe}</h2><p>来源：{study.source}。仅拉取当前标的的历史 K 线，不执行全市场扫描。</p></div><span className="pill">{study.currency}</span></div><div className="metric-grid"><Metric label="趋势" value={study.assessment.trend} /><Metric label="动量" value={study.assessment.momentum} /><Metric label="量能压力" value={study.assessment.volume_pressure} /><Metric label="RSI(14)" value={String(indicators.rsi_14 ?? "—")} /></div><section className="chart-box"><h3>K 线价格区间</h3><div className="candle-strip">{study.bars.slice(-60).map((bar) => { const up = Number(bar.close) >= Number(bar.open); return <span title={`${bar.date} O:${bar.open} H:${bar.high} L:${bar.low} C:${bar.close}`} className={up ? "candle up" : "candle down"} key={bar.date} style={{ height: `${Math.max(8, Math.min(100, (Number(bar.high) - Number(bar.low)) * 10))}%` }} />; })}</div><div className="indicator-row">MA5 {indicators.sma_5 ?? "—"} · MA10 {indicators.sma_10 ?? "—"} · MA20 {indicators.sma_20 ?? "—"} · MA60 {indicators.sma_60 ?? "—"} · MACD {indicators.macd ?? "—"} · ATR {indicators.atr_14 ?? "—"}</div></section><section className="profile-box"><div><h3>Volume Profile 水平成交量分布</h3><p>POC {profile.point_of_control ?? "—"} · 70% 价值区 {profile.value_area_low ?? "—"} — {profile.value_area_high ?? "—"}</p></div><div className="profile-levels">{profile.levels.slice().reverse().map((level) => <div className="profile-level" key={String(level.price)}><span>{level.price}</span><i style={{ width: `${Math.max(2, Number(level.volume) / maxVolume * 100)}%` }} /><b>{level.percent}%</b></div>)}</div></section><section className="analysis-box"><h3>规则化解读</h3><ul>{study.assessment.observations.map((item) => <li key={item}>{item}</li>)}</ul><p>AI 提问时可直接填写相同标的，系统会结合行情、资讯、基本面与个人策略补充解读。</p>{study.assessment.limitations.map((item) => <small key={item}>{item}</small>)}</section></div>;
}

function NewsWorkspace() {
  const [news, setNews] = useState<NewsItem[]>([]); const [error, setError] = useState<string | null>(null); const [loading, setLoading] = useState(false);
  async function load() { setLoading(true); setError(null); try { setNews(await fetchNews()); } catch (reason) { setError(reason instanceof Error ? reason.message : "资讯请求失败"); } finally { setLoading(false); } }
  return <section className="panel"><div className="panel-head"><div><h2>近 24 小时财经快讯</h2><p>东方财富优先，失败时自动尝试新浪；成功结果短时缓存，减少公开源限频风险。资讯显示可解释词典情绪，仅供研究。</p></div><button className="secondary" onClick={load} disabled={loading}>{loading ? "采集中…" : "采集资讯"}</button></div>{error && <div className="notice">{error}</div>}<div className="news-list">{news.map((item) => <article className="news-item" key={`${item.publisher}-${item.published_at}-${item.title}`}><span className={`tag ${item.sentiment}`}>{item.sentiment}</span><h3>{item.title}</h3><p>{item.content}</p><small>{item.publisher} · {new Date(item.published_at).toLocaleString()} · 情绪 {item.sentiment_score}</small></article>)}</div></section>;
}

function ResearchWorkspace() {
  const [symbol, setSymbol] = useState("600519.SH"); const [market, setMarket] = useState<Market>("a_share");
  const [instrumentType, setInstrumentType] = useState<InstrumentType>("equity");
  const [report, setReport] = useState<ResearchReport | null>(null); const [error, setError] = useState<string | null>(null); const [loading, setLoading] = useState(false);
  async function submit(event: FormEvent) { event.preventDefault(); setLoading(true); setError(null); try { setReport(await fetchResearch(symbol, market, instrumentType)); } catch (reason) { setError(reason instanceof Error ? reason.message : "研究请求失败"); } finally { setLoading(false); } }
  return <section className="panel"><form onSubmit={submit}><TickerFields symbol={symbol} market={market} setSymbol={setSymbol} setMarket={setMarket} /><InstrumentTypeField value={instrumentType} setValue={setInstrumentType} /><button className="primary" disabled={loading}>{loading ? "分析中…" : "运行研究分析"}</button></form>{error && <div className="notice">{error}</div>}{report && <div className="research-results"><DataCard title="基本面" data={report.fundamentals} /><DataCard title="资金流" data={report.capital_flow} /><DataCard title="新闻情绪" data={report.news_sentiment} />{report.fund_research && <DataCard title="基金 / ETF 专项数据" data={report.fund_research} />}{report.notices.map((item) => <div className="notice" key={item}>{item}</div>)}</div>}</section>;
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
