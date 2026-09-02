import { useEffect, useState } from "react";
import { Factor, fetchFactors } from "./api";

type Page = "dashboard" | "markets" | "news" | "research" | "factors" | "strategies" | "documents" | "journal" | "settings";

const navigation: Array<{ id: Page; label: string; description: string }> = [
  { id: "dashboard", label: "总览", description: "数据与研究工作台" },
  { id: "markets", label: "行情", description: "A 股 / 港股 / 美股 / ETF" },
  { id: "news", label: "财经资讯", description: "采集与大模型解读" },
  { id: "research", label: "研究分析", description: "基本面、情绪、资金流、期权" },
  { id: "factors", label: "因子库", description: "定义、验证、版本" },
  { id: "strategies", label: "个人策略", description: "注入、验证、回测" },
  { id: "documents", label: "文档 / OCR", description: "研报与证据提取" },
  { id: "journal", label: "交易日志", description: "导入、归因、复盘" },
  { id: "settings", label: "设置", description: "私有部署与连接配置" }
];

const capabilityCards = [
  ["基本面", "已实现领域分析", "指标以公告日对齐"],
  ["情绪", "已实现新闻分析", "词典基线 + 可选 LLM"],
  ["资金流", "已实现领域分析", "净流入与大单方向"],
  ["期权", "已实现领域分析", "到期盈亏与风险边界"]
];

function App() {
  const [page, setPage] = useState<Page>("dashboard");
  const [factors, setFactors] = useState<Factor[]>([]);
  const [factorError, setFactorError] = useState<string | null>(null);

  useEffect(() => {
    if (page !== "factors") return;
    fetchFactors().then(setFactors).catch((error: Error) => setFactorError(error.message));
  }, [page]);

  const active = navigation.find((item) => item.id === page)!;
  return (
    <main className="shell">
      <aside className="sidebar">
        <div className="brand"><span>◈</span><div><strong>My AI</strong><small>Trading Agent</small></div></div>
        <nav aria-label="功能导航">
          {navigation.map((item) => <button key={item.id} className={page === item.id ? "nav active" : "nav"} onClick={() => setPage(item.id)}>{item.label}</button>)}
        </nav>
        <div className="security">私有模式<br /><small>密钥仅在你的环境变量中</small></div>
      </aside>
      <section className="content">
        <header><div><p className="eyebrow">RESEARCH WORKSPACE</p><h1>{active.label}</h1><p>{active.description}</p></div><span className="pill">私有服务器就绪</span></header>
        {page === "dashboard" && <Dashboard onNavigate={setPage} />}
        {page === "factors" && <FactorLibrary factors={factors} error={factorError} />}
        {page !== "dashboard" && page !== "factors" && <ComingSoon page={active.label} />}
      </section>
    </main>
  );
}

function Dashboard({ onNavigate }: { onNavigate: (page: Page) => void }) {
  return <>
    <section className="hero"><div><p className="eyebrow">RESEARCH-FIRST QUANT</p><h2>从数据、新闻到可审计策略</h2><p>前端不会保存 Token；所有供应商连接与模型密钥只由后端私有环境处理。</p></div><button className="primary" onClick={() => onNavigate("factors")}>查看因子库</button></section>
    <div className="grid four">{capabilityCards.map(([name, status, detail]) => <article className="card" key={name}><p className="muted">{status}</p><h3>{name}</h3><p>{detail}</p></article>)}</div>
    <section className="roadmap"><h2>工作流入口</h2><div className="grid three">{navigation.slice(1).map((item) => <button className="feature" key={item.id} onClick={() => onNavigate(item.id)}><strong>{item.label}</strong><span>{item.description}</span><b>进入 →</b></button>)}</div></section>
  </>;
}

function FactorLibrary({ factors, error }: { factors: Factor[]; error: string | null }) {
  return <section className="panel"><div className="panel-head"><div><h2>声明式因子注册表</h2><p>公式仅作审计说明，不执行用户输入的任意代码；验证使用同一时点因子与未来收益。</p></div><button className="secondary" onClick={() => location.reload()}>重新加载</button></div>{error && <div className="notice">{error}。请先启动 Python 后端。</div>}
    {!error && factors.length === 0 && <p className="muted">正在读取后端因子库…</p>}
    <div className="factor-list">{factors.map((factor) => <article className="factor" key={factor.identifier}><div><span className="tag">{factor.theme}</span><h3>{factor.name}</h3><code>{factor.formula}</code><p>{factor.description}</p></div><dl><div><dt>输入</dt><dd>{factor.columns_required.join(", ")}</dd></div><div><dt>预热</dt><dd>{factor.warmup_bars} bars</dd></div><div><dt>持有期</dt><dd>{factor.horizon_days} 天</dd></div></dl></article>)}</div>
  </section>;
}

function ComingSoon({ page }: { page: string }) {
  return <section className="panel empty"><p className="eyebrow">MODULE BOUNDARY READY</p><h2>{page}工作台</h2><p>页面入口、独立 API 边界和数据库对象已经预留。下一步会连接对应的后端用例，任何写入前均保留审计记录。</p><button className="secondary" disabled>等待后端用例接入</button></section>;
}

export default App;
