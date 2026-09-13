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

export interface InstrumentIdentity {
  symbol: string;
  market: Market;
  instrument_type: InstrumentType;
  display_name: string | null;
  source: string | null;
}

export interface MarketIndexSnapshot {
  symbol: string;
  name: string;
  last_price: string;
  price_change: string | null;
  change_percent: string | null;
}

export interface SectorRotationItem {
  symbol: string;
  name: string;
  last_price: string;
  change_percent: string;
}

export interface PostMarketBrief {
  observed_at: string;
  source: string;
  indices: MarketIndexSnapshot[];
  leading_sectors: SectorRotationItem[];
  lagging_sectors: SectorRotationItem[];
  coverage: string;
  disclaimer: string;
}
export interface MarketQuestionCandidate {
  symbol: string;
  name: string;
  asset_type: string;
  exchange: string | null;
  currency: string | null;
  source: string;
}
export interface MarketQuestionAnswer {
  answer: string;
  generated_at: string;
  sources: string[];
  notices: string[];
  candidates: MarketQuestionCandidate[];
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
  factor_analysis: Record<string, unknown> | null;
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

export interface WatchlistInput { symbol: string; market: Market; instrument_type: InstrumentType; label: string; notes: string; }
export interface WatchlistItem extends WatchlistInput { item_id: string; display_name: string | null; }
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
export interface IncomeStatementSummary { report_period: string; announced_on: string; currency: string; operating_income: string | null; operating_profit: string | null; net_profit: string | null; basic_eps: string | null; }
export interface BalanceSheetSummary { report_period: string; currency: string; total_assets: string | null; total_debt: string | null; total_equity: string | null; cash: string | null; accounts_receivable: string | null; debt_to_assets_percent: string | null; }
export interface CashFlowSummary { report_period: string; currency: string; operating_cash_flow: string | null; investing_cash_flow: string | null; financing_cash_flow: string | null; net_cash_change: string | null; }
export interface ValuationSummary { observed_at: string | null; price_to_earnings_ttm: string | null; price_to_earnings_mrq: string | null; price_to_book_mrq: string | null; price_to_sales_ttm: string | null; price_to_cash_flow_ttm: string | null; }
export interface TimeCatalyst { occurred_on: string; title: string; detail: string; kind: string; }
export interface WatchlistFinancialDetail { symbol: string; market: Market; instrument_type: InstrumentType; observed_at: string; source: string; income_statement: IncomeStatementSummary | null; balance_sheet: BalanceSheetSummary | null; cash_flow: CashFlowSummary | null; valuation: ValuationSummary | null; time_catalysts: TimeCatalyst[]; notices: string[]; }
export interface PaperPositionInput { symbol: string; market: Market; instrument_type: InstrumentType; quantity: string; average_cost: string; notes: string; }
export interface PaperPosition extends PaperPositionInput { position_id: string; display_name: string | null; cost_amount: string; }
export interface PaperPositionValuation extends PaperPosition { last_price: string; currency: string; observed_at: string; source: string; market_value: string; unrealized_pnl: string; unrealized_pnl_percent: string; daily_pnl: string | null; daily_pnl_percent: string | null; month_to_date_pnl: string | null; month_to_date_pnl_percent: string | null; month_reference_date: string | null; }
export interface PaperPortfolioCurrencySummary { currency: string; position_count: number; initial_principal: string; total_market_value: string; cumulative_pnl: string; cumulative_return_percent: string; daily_pnl: string | null; daily_return_percent: string | null; month_to_date_pnl: string | null; month_to_date_return_percent: string | null; daily_coverage_count: number; month_coverage_count: number; }
export interface PaperPortfolioOverview { observed_at: string; valued_position_count: number; total_position_count: number; currencies: PaperPortfolioCurrencySummary[]; valuations: PaperPositionValuation[]; notices: string[]; }
export interface AiSimulationRunInput { market: Exclude<Market, "fund">; initial_capital: string; max_positions: number; strategy_id: string | null; }
export interface AiSimulationPosition { position_id: string; symbol: string; display_name: string | null; market: Market; instrument_type: InstrumentType; quantity: string; average_cost: string; cost_amount: string; candidate_score: string; factor_context: string[]; rationale: string[]; opened_at: string; last_price: string | null; market_value: string | null; unrealized_pnl: string | null; unrealized_pnl_percent: string | null; daily_pnl: string | null; month_to_date_pnl: string | null; source: string | null; }
export interface AiSimulationDecision { symbol: string; display_name: string | null; score: string; decision: "buy" | "skip" | "already_held"; supportive_factor_count: number; adverse_factor_count: number; available_factor_ids: string[]; unavailable_factor_ids: string[]; blockers: string[]; }
export interface AiSimulationOverview { portfolio_id: string; market: Market; currency: string; initial_capital: string; cash_balance: string; invested_cost: string; market_value: string; total_equity: string; cumulative_pnl: string; daily_pnl: string | null; month_to_date_pnl: string | null; max_positions: number; strategy_id: string | null; observed_at: string; positions: AiSimulationPosition[]; notices: string[]; decision_reports: AiSimulationDecision[]; }

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
export const resolveInstrument = (symbol: string, market: Market, instrumentType: InstrumentType = "equity") =>
  request<InstrumentIdentity>("/api/v1/instruments/resolve", { method: "POST", body: JSON.stringify({ symbol, market, instrument_type: instrumentType }) });
export const fetchPostMarketBrief = (refresh = false) =>
  request<PostMarketBrief>(`/api/v1/market/post-market-brief?refresh=${refresh}`);
export const askMarketQuestion = (question: string) =>
  request<MarketQuestionAnswer>("/api/v1/assistant/market-question", {
    method: "POST", body: JSON.stringify({ question })
  });
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
export const fetchTechnicalStudy = (symbol: string, market: Market, timeframe: TechnicalTimeframe, instrumentType: InstrumentType = "equity", limit = 180) =>
  request<TechnicalStudy>("/api/v1/technical/study", { method: "POST", body: JSON.stringify({ symbol, market, instrument_type: instrumentType, timeframe, limit }) });
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
export const fetchWatchlistDeepDive = (itemId: string) => request<WatchlistFinancialDetail>(`/api/v1/watchlist/${itemId}/deep-dive`);
export const fetchPaperPositions = () => request<PaperPosition[]>("/api/v1/paper-positions");
export const createPaperPosition = (payload: PaperPositionInput) => request<PaperPosition>("/api/v1/paper-positions", { method: "POST", body: JSON.stringify(payload) });
export const deletePaperPosition = (positionId: string) => request<void>(`/api/v1/paper-positions/${positionId}`, { method: "DELETE" });
export const fetchPaperValuations = () => request<PaperPositionValuation[]>("/api/v1/paper-positions/valuations");
export const fetchPaperPortfolioOverview = () => request<PaperPortfolioOverview>("/api/v1/paper-positions/overview");
export const fetchAiSimulationOverview = (market: Exclude<Market, "fund">) => request<AiSimulationOverview>(`/api/v1/ai-simulation/overview?market=${market}`);
export const runAiSimulation = (payload: AiSimulationRunInput) => request<AiSimulationOverview>("/api/v1/ai-simulation/run", { method: "POST", body: JSON.stringify(payload) });
export const updateAiSimulationSettings = (payload: AiSimulationRunInput) => request<AiSimulationOverview>("/api/v1/ai-simulation/settings", { method: "PUT", body: JSON.stringify(payload) });
