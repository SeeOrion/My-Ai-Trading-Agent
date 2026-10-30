import { useEffect, useState } from "react";
import { fetchLLMUsage, LLMUsage } from "./api";

const features: Record<string, string> = { watchlist_auto: "自动摘要", watchlist_manual: "手动摘要", market_question: "市场问答", research: "其他研究" };
const statuses: Record<string, string> = { success: "成功", failed: "失败", reused: "复用摘要" };
const number = (value: number | null) => value === null ? "未报告" : value.toLocaleString("zh-CN");

export function LLMUsagePanel() {
  const [period, setPeriod] = useState<"day" | "month">("month");
  const [data, setData] = useState<LLMUsage | null>(null);
  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    let active = true;
    setError(""); setData(null);
    fetchLLMUsage(period).then(value => { if (active) setData(value); })
      .catch(() => { if (active) setError("用量统计暂不可用，请稍后刷新。"); });
    return () => { active = false; };
  }, [period, refresh]);
  const groups = data?.groups ?? [];
  const calls = groups.filter(g => g.status !== "reused");
  const reused = groups.filter(g => g.status === "reused").reduce((sum, g) => sum + g.events, 0);
  const total = calls.reduce((sum, g) => sum + (g.total_tokens ?? 0), 0);
  const unknown = calls.reduce((sum, g) => sum + g.unknown_usage, 0);
  return <section className="panel">
    <div className="panel-head"><h2>大模型用量统计</h2><button className="secondary" onClick={() => setRefresh(v => v + 1)}>刷新统计</button></div>
    <label>统计范围（UTC）<select value={period} onChange={e => setPeriod(e.target.value as "day" | "month")}><option value="day">今日</option><option value="month">本月</option></select></label>
    <p>交易时段模拟复核保持每 10 分钟；自选研究默认每小时检查。关键状态没有明显变化时复用摘要，尾盘自动检查也遵守复用规则。手动更新可重新生成。</p>
    {error ? <p className="notice">{error}</p> : !data ? <p>正在读取用量…</p> : <>
      <p>模型请求 {calls.reduce((sum, g) => sum + g.events, 0)} 次 · 复用摘要 {reused} 次 · 已报告 Token {number(total)}</p>
      {unknown > 0 && <p className="notice">{unknown} 次请求未报告完整用量，以上合计不代表完整账单。</p>}
      <div style={{ overflowX: "auto" }}><table><thead><tr><th>功能 / 模型</th><th>结果</th><th>次数</th><th>输入</th><th>输出</th><th>总量</th><th>缓存输入</th><th>推理</th></tr></thead><tbody>{groups.map((g, index) => <tr key={index}><td>{features[g.feature] ?? "其他研究"}<br />{g.model || "无需模型"}</td><td>{statuses[g.status] ?? g.status}</td><td>{g.events}</td>{([g.input_tokens, g.output_tokens, g.total_tokens, g.cached_tokens, g.reasoning_tokens]).map((v, i) => <td key={i}>{g.status === "reused" ? "—" : number(v)}</td>)}</tr>)}</tbody></table></div>
      {!groups.length && <p>尚无记录。统计从本次升级后开始，不回填历史账单。</p>}
    </>}
    <p>缓存输入与推理 Token 是明细，不额外累加到总量。不保存提示词、回答正文或密钥；费用以服务商账单为准。</p>
  </section>;
}
