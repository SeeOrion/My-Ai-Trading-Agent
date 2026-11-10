import { useEffect, useState } from "react";
import { AgentSettings, AgentAudit, fetchAgentSettings, saveAgentSettings, fetchAgentAudits } from "./api";

const labels: Record<string,string> = {completed:"完成", failed:"失败", timeout:"超时", insufficient_evidence:"证据不足", disabled:"已关闭或配置变化", token_limit:"达到用量上限", round_limit:"达到轮数上限", repeat_limit:"重复查询受限", usage_unknown:"用量未报告", invalid_tool:"工具参数无效", buy:"买入", skip:"跳过", hold:"持有", reduce:"减仓", exit:"退出", wait:"暂缓", pending:"等待规则审核", approved:"规则审核通过", full_exit:"清仓", partial_exit:"减仓", intact:"假设成立", weakened:"假设削弱", invalidated:"假设失效", unverifiable:"无法验证", event_veracity:"事件可信度", earnings_persistence:"盈利持续性", thesis_resilience:"假设抗风险性", quote:"行情", financials:"财务", news:"新闻", capital_flow:"资金流", factors:"因子", technical:"技术指标", position:"持仓检验", critical:"关键风险", major:"重大风险", minor:"一般风险"};
Object.assign(labels, {running:"研究中", cancelled:"已取消", unavailable:"数据暂不可用"});
const label = (value: string) => labels[value] ?? value;

export function AgentSettingsPanel({ accountId }: {accountId: string}) {
  const [config, setConfig] = useState<AgentSettings | null>(null);
  const [audits, setAudits] = useState<AgentAudit[]>([]);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { let active = true; Promise.all([fetchAgentSettings(accountId), fetchAgentAudits(accountId)]).then(([c,a]) => {if(active){setConfig(c.settings);setAudits(a);}}).catch(() => {if(active)setMessage("研究配置暂不可用，请重新打开账户设置。");}); return () => {active=false;}; }, [accountId]);
  async function save(disable = false) {
    if (!config) return;
    setBusy(true);
    try {
      const next = disable ? {...(await fetchAgentSettings(accountId)).settings, position_enabled:false} : config;
      const result = await saveAgentSettings(accountId, next); setConfig(result.settings);
      setMessage(disable ? "持仓检验已关闭，旧研究结果不再用于后续交易。" : "本账户研究配置已保存；新配置从后续复核生效。");
    } catch (e) {setMessage(e instanceof Error ? e.message : "保存失败");} finally {setBusy(false);}
  }
  if (!config) return <p>{message || "正在读取研究配置…"}</p>;
  const fields: Array<[keyof AgentSettings,string,number,number,number]> = [["workflow_weight","基础评分权重",0,1,.05],["research_weight","研究评分权重",0,1,.05],["entry_threshold","综合评分门槛",0,100,1],["holding_days","预期持有天数",1,3650,1],["max_price_move","研究期间允许价格偏移（0.02=2%）",0,.1,.005],["validity_seconds","研究与报价有效期（秒）",30,1800,30],["rounds","最多研究轮数",2,10,1],["tokens","每次研究 Token 预算",1000,20000,1000],["timeout_seconds","研究超时（秒）",5,90,5],["repeated_queries","相同查询最多次数",1,2,1]];
  return <section className="panel"><h3>本账户研究 Agent</h3><p>买入研究固定启用。评分为研究尺度，权重与门槛是待验证参数，不代表盈利概率；个人纪律、资金及仓位约束独立执行。</p>
    <label className="check"><input type="checkbox" checked={config.position_enabled} onChange={e=>setConfig({...config,position_enabled:e.target.checked})}/>启用持仓假设检验（保存后生效）</label>
    <button className="secondary" disabled={busy} onClick={()=>void save(true)}>立即关闭持仓检验</button>
    <div className="ai-simulation-controls">{fields.map(([key,title,min,max,step])=><label key={key}>{title}<input type="number" min={min} max={max} step={step} value={String(config[key])} onChange={e=>setConfig({...config,[key]:typeof config[key]==="number"?Number(e.target.value):e.target.value})}/></label>)}</div>
    <button className="primary" disabled={busy} onClick={()=>void save()}>保存研究配置</button>{message&&<p className="notice">{message}</p>}
    <div className="panel-head"><h3>研究与规则审核记录</h3><button className="secondary" onClick={()=>fetchAgentAudits(accountId).then(setAudits).catch(()=>setMessage("研究记录读取失败"))}>刷新研究记录</button></div>
    {!audits.length&&<p>尚无研究记录；下一轮模拟会记录候选研究与规则审核结果。</p>}
    {audits.map(a=><details key={a.audit_id}><summary>{a.symbol} · {a.kind==="buy"?"买入研究":"持仓检验"} · {label(a.status)} · {label(a.rule_review.action)} · {new Date(a.created_at).toLocaleString()}</summary>
      <p>基础分 {a.rule_review.workflow_score??"—"} / 研究分 {a.rule_review.research_score??a.report?.score??"—"} / 综合分 {a.rule_review.combined_score??"—"} · 用量 {a.tokens}</p>
      {a.rule_review.blockers?.map((b,i)=><p key={i}>{b}</p>)}
      {a.report&&<><p>买入假设：{a.report.thesis.text}</p><p>{label(a.report.thesis_state)} · 建议{label(a.report.recommendation)}</p>{Object.entries(a.report.dimensions).map(([key,d])=><p key={key}>{label(key)}：{d.score}，权重 {d.weight} · {d.text}</p>)}{a.report.support.map((s,i)=><p key={"s"+i}>支持：{s.text}</p>)}{a.report.opposition.map((s,i)=><p key={"o"+i}>反对：{s.text}</p>)}{a.report.risks.map((r,i)=><p key={"r"+i}>{label(r.severity)}：{r.text}<br/>原文依据：{r.source_quote}</p>)}{a.report.data_gaps.map((s,i)=><p key={"g"+i}>缺口：{s}</p>)}</>}
      <p>查询记录：{a.trace.map(t=>`${label(t.tool)}（${label(t.status)}，${new Date(t.started_at).toLocaleTimeString()}）`).join(" → ")}</p>
    </details>)}
  </section>;
}
