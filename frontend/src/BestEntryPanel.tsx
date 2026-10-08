import { useEffect, useState } from "react";
import { BestEntries, fetchBestEntries, Market } from "./api";

/** Read-only preview; never creates accounts or orders. */
export function BestEntryPanel() {
  const [market, setMarket] = useState<Exclude<Market, "fund">>("a_share");
  const [revision, setRevision] = useState(0);
  const [result, setResult] = useState<BestEntries | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setResult(null); setError("");
    fetchBestEntries(market, controller.signal).then(data => {
      if (!controller.signal.aborted) setResult(data);
    }).catch((reason: unknown) => {
      if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : "筛选暂不可用");
    }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [market, revision]);
  return <section className="panel best-entry-panel" aria-busy={loading}>
    <div className="panel-head"><div><p className="eyebrow">数据驱动 · 模拟买入规则</p><h2>今日最佳三只股票</h2><p>当前研究样本中最符合入场规则的候选，不代表全市场最优，也不会自动下单。</p></div>
      <div className="best-entry-controls"><label>市场 <select value={market} onChange={event => setMarket(event.target.value as Exclude<Market, "fund">)}><option value="a_share">A 股</option><option value="hong_kong">港股</option><option value="united_states">美股</option></select></label><button className="secondary" disabled={loading} onClick={() => setRevision(value => value + 1)}>重新筛选</button></div></div>
    {loading && <p role="status" className="muted">正在复核行情、因子、策略、个人纪律与账户预算，可继续浏览其他模块…</p>}
    {error && <div className="notice" role="alert">{error}</div>}
    {result && <><p className="brief-note">{result.account_basis}<br />{result.coverage} 样本数：{result.universe_size} · 快照于 {new Date(result.refreshed_at).toLocaleString()}</p>
      {result.candidates.length < 3 && <div className="notice">本次有 {result.candidates.length} 只符合入场条件。休市后行情过期、预算不足或条件未达标时不会凑足三只。</div>}
      <div className="best-entry-grid">{result.candidates.map((item, index) => <article className="best-entry-card" key={item.symbol}><div className="panel-head"><strong>{index + 1}. {item.name || item.symbol}</strong><span className="tag info">综合评分 {Number(item.score).toFixed(1)}</span></div><small>{item.symbol} · {item.source}</small><h3>{Number(item.price).toLocaleString(undefined, { maximumFractionDigits: 4 })}</h3><small>行情时间 {new Date(item.observed_at).toLocaleString()}</small><div className="best-entry-tags"><span className="tag">支持因子 {item.supportive}</span><span className="tag">不利因子 {item.adverse}</span><span className="tag">缺失因子 {item.missing_factors.length}</span></div><ul>{item.reasons.map((reason, i) => <li key={i}>{reason}</li>)}</ul></article>)}</div>
      {result.excluded.length > 0 && <details className="best-entry-excluded"><summary>查看未入选原因（{result.excluded.length}）</summary>{result.excluded.map(item => <p key={item.symbol}><strong>{item.symbol}</strong>：{item.reasons.join("；")}</p>)}</details>}
      <small className="muted">各候选独立评估，不表示可以同时买入全部候选。缺失因子仅提示，明确不利因子、未满足的个人纪律及资金约束仍会阻止入选。仅供研究，不保证收益。</small></>}
  </section>;
}
