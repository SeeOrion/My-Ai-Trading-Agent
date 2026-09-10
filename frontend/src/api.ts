export type Market = "a_share" | "hong_kong" | "united_states" | "fund";
export type InstrumentType = "equity" | "etf" | "fund" | "option";

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

export type CandidateRanking = "composite" | "momentum" | "balanced_entry";

export interface MarketCandidate {
  symbol: string;
  name: string;
  market: Market;
  currency: string;
  last_price: string;
  change_percent: string | null;
  score: string;
  reasons: string[];
  observed_at: string;
  source: string;
}

export interface CandidateScreen {
  market: Market;
  ranking: CandidateRanking;
  candidates: MarketCandidate[];
  universe_size: number;
  refreshed_at: string;
  source: string;
  coverage: string;
  disclaimer: string;
}

export interface MarketScanRun {
  run_id: string;
  market: Market;
  source: string;
  status: "completed" | "failed";
  started_at: string;
  completed_at: string;
  universe_size: number;
  snapshot_count: number;
  error_message: string | null;
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
  fund_research: Record<string, unknown> | null;
  notices: string[];
}

export interface FundResearch { symbol: string; market: Market; fund: Record<string, unknown>; }

export type TechnicalTimeframe = "1d" | "1w" | "1m";
export type NumericValue = string | number | null;
export interface TechnicalBar { date: string; open: NumericValue; high: NumericValue; low: NumericValue; close: NumericValue; volume: NumericValue; }
export interface TechnicalStudy { symbol: string; market: Market; currency: string; timeframe: TechnicalTimeframe; source: string; bars: TechnicalBar[]; indicators: Record<string, NumericValue>; volume_profile: { point_of_control: NumericValue; value_area_low: NumericValue; value_area_high: NumericValue; value_area_percent: NumericValue; method: string; levels: Array<{ price: NumericValue; volume: NumericValue; percent: NumericValue }> }; assessment: { trend: string; momentum: string; volume_pressure: string; observations: string[]; limitations: string[] }; }

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
  instrument_type: InstrumentType;
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

export type DisciplineDecisionStatus = "observe" | "buy_candidate" | "add_condition_met" | "take_profit" | "exit";
export interface DisciplineDecision {
  discipline_id: string;
  discipline_name: string;
  symbol: string;
  market: Market;
  instrument_type: InstrumentType;
  status: DisciplineDecisionStatus;
  label: string;
  last_price: string;
  matched_level: string | null;
  rationale: string;
}

export interface WatchlistInput { symbol: string; market: Market; instrument_type: InstrumentType; label: string; notes: string; }
export interface WatchlistItem extends WatchlistInput { item_id: string; }
export interface WatchlistAnalysisTag { category: string; label: string; tone: "positive" | "negative" | "neutral" | "info"; }
export interface WatchlistAnalysis {
  analysis_id: string;
  watchlist_item_id: string;
  symbol: string;
  market: Market;
  instrument_type: InstrumentType;
  observed_at: string;
  status: "completed" | "partial" | "failed";
  tags: WatchlistAnalysisTag[];
  ai_summary: string | null;
  notices: string[];
}
export interface PaperPositionInput { symbol: string; market: Market; instrument_type: InstrumentType; quantity: string; average_cost: string; notes: string; }
export interface PaperPosition extends PaperPositionInput { position_id: string; }
export interface PaperPositionValuation extends PaperPosition { last_price: string; currency: string; observed_at: string; source: string; market_value: string; unrealized_pnl: string; unrealized_pnl_percent: string; }

export interface ChatResult {
  answer: string;
  context_status: string[];
  discipline_decisions?: DisciplineDecision[];
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
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const fetchFactors = () => request<Factor[]>("/api/v1/factors");
export const fetchQuote = (symbol: string, market: Market, instrumentType: InstrumentType = "equity") =>
  request<Quote>("/api/v1/market/quote", { method: "POST", body: JSON.stringify({ symbol, market, instrument_type: instrumentType }) });
export const fetchCandidates = (market: Market, ranking: CandidateRanking, refresh = false) =>
  request<CandidateScreen>(`/api/v1/market/candidates?market=${market}&ranking=${ranking}&refresh=${refresh}`);
export const runMarketScan = (market: Market) =>
  request<MarketScanRun>(`/api/v1/market/scans/${market}`, { method: "POST" });
export const fetchLatestMarketScan = (market: Market) =>
  request<MarketScanRun>(`/api/v1/market/scans/${market}/latest`);
export const fetchNews = () => request<NewsItem[]>("/api/v1/news?source=eastmoney&source=sina");
export const fetchResearch = (symbol: string, market: Market, instrumentType: InstrumentType = "equity") =>
  request<ResearchReport>("/api/v1/research", {
    method: "POST",
    body: JSON.stringify({ symbol, market, instrument_type: instrumentType, news_sources: ["eastmoney", "sina"] })
  });
export const fetchFundResearch = (symbol: string, market: Market, instrumentType: InstrumentType) =>
  request<FundResearch>("/api/v1/funds/research", { method: "POST", body: JSON.stringify({ symbol, market, instrument_type: instrumentType }) });
export const fetchTechnicalStudy = (symbol: string, market: Market, timeframe: TechnicalTimeframe, instrumentType: InstrumentType = "equity") =>
  request<TechnicalStudy>("/api/v1/technical/study", { method: "POST", body: JSON.stringify({ symbol, market, instrument_type: instrumentType, timeframe, limit: 180 }) });
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
export const fetchWatchlist = () => request<WatchlistItem[]>("/api/v1/watchlist");
export const createWatchlistItem = (payload: WatchlistInput) => request<WatchlistItem>("/api/v1/watchlist", { method: "POST", body: JSON.stringify(payload) });
export const deleteWatchlistItem = (itemId: string) => request<void>(`/api/v1/watchlist/${itemId}`, { method: "DELETE" });
export const fetchWatchlistAnalyses = () => request<WatchlistAnalysis[]>("/api/v1/watchlist/analyses");
export const fetchWatchlistAnalysis = (itemId: string) => request<WatchlistAnalysis>(`/api/v1/watchlist/${itemId}/analysis`);
export const refreshWatchlistAnalysis = (itemId: string) => request<WatchlistAnalysis>(`/api/v1/watchlist/${itemId}/analysis/refresh`, { method: "POST" });
export const fetchPaperPositions = () => request<PaperPosition[]>("/api/v1/paper-positions");
export const createPaperPosition = (payload: PaperPositionInput) => request<PaperPosition>("/api/v1/paper-positions", { method: "POST", body: JSON.stringify(payload) });
export const deletePaperPosition = (positionId: string) => request<void>(`/api/v1/paper-positions/${positionId}`, { method: "DELETE" });
export const fetchPaperValuations = () => request<PaperPositionValuation[]>("/api/v1/paper-positions/valuations");
export const askAssistant = (payload: {
  question: string;
  symbol?: string;
  market?: Market;
  instrument_type?: InstrumentType;
  strategy_id?: string;
}) => request<ChatResult>("/api/v1/assistant/chat", { method: "POST", body: JSON.stringify(payload) });
