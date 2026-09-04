export type Market = "a_share" | "hong_kong" | "united_states";

export interface Factor {
  identifier: string;
  name: string;
  theme: string;
  formula: string;
  columns_required: string[];
  warmup_bars: number;
  horizon_days: number;
  description: string;
  version: string;
}

export interface Quote {
  symbol: string;
  market: Market;
  currency: string;
  last_price: string;
  observed_at: string;
  source: string;
  open_price: string | null;
  high_price: string | null;
  low_price: string | null;
  previous_close: string | null;
  volume: string | null;
}

export interface NewsItem {
  title: string;
  content: string;
  publisher: string;
  published_at: string;
  url: string | null;
  sentiment: string;
  sentiment_score: string;
}

export interface ResearchReport {
  symbol: string;
  market: Market;
  fundamentals: Record<string, unknown> | null;
  capital_flow: Record<string, unknown> | null;
  news_sentiment: Record<string, unknown> | null;
  notices: string[];
}

export interface StrategyInput {
  name: string;
  thesis: string;
  factor_ids: string[];
  markets: Market[];
  max_position_pct: string;
  risk_notes: string;
  status: "draft" | "active" | "archived";
}

export interface Strategy extends StrategyInput {
  strategy_id: string;
  version: number;
}

export interface DisciplineInput {
  name: string;
  symbol: string;
  market: Market;
  instrument_type: "equity" | "etf" | "option";
  buy_price: string;
  add_price: string | null;
  take_profit_price: string;
  exit_price: string;
  notes: string;
  status: "active" | "paused" | "archived";
}

export interface Discipline extends DisciplineInput {
  discipline_id: string;
  version: number;
}

export interface ChatResult {
  answer: string;
  context_status: string[];
  disclaimer: string;
}

const apiBase = import.meta.env.VITE_API_BASE_URL ?? "";

export class ApiError extends Error {}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBase}${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as { detail?: string };
    throw new ApiError(body.detail ?? `请求失败（${response.status}）`);
  }
  return response.json() as Promise<T>;
}

export const fetchFactors = () => request<Factor[]>("/api/v1/factors");
export const fetchQuote = (symbol: string, market: Market) =>
  request<Quote>("/api/v1/market/quote", { method: "POST", body: JSON.stringify({ symbol, market }) });
export const fetchNews = () => request<NewsItem[]>("/api/v1/news?source=sina");
export const fetchResearch = (symbol: string, market: Market) =>
  request<ResearchReport>("/api/v1/research", {
    method: "POST",
    body: JSON.stringify({ symbol, market, news_sources: ["sina"] })
  });
export const fetchStrategies = () => request<Strategy[]>("/api/v1/strategies");
export const createStrategy = (payload: StrategyInput) =>
  request<Strategy>("/api/v1/strategies", { method: "POST", body: JSON.stringify(payload) });
export const updateStrategy = (strategyId: string, payload: StrategyInput) =>
  request<Strategy>(`/api/v1/strategies/${strategyId}`, { method: "PUT", body: JSON.stringify(payload) });
export const fetchDisciplines = () => request<Discipline[]>("/api/v1/disciplines");
export const createDiscipline = (payload: DisciplineInput) =>
  request<Discipline>("/api/v1/disciplines", { method: "POST", body: JSON.stringify(payload) });
export const updateDiscipline = (disciplineId: string, payload: DisciplineInput) =>
  request<Discipline>(`/api/v1/disciplines/${disciplineId}`, { method: "PUT", body: JSON.stringify(payload) });
export const askAssistant = (payload: {
  question: string;
  symbol?: string;
  market?: Market;
  strategy_id?: string;
}) => request<ChatResult>("/api/v1/assistant/chat", { method: "POST", body: JSON.stringify(payload) });
