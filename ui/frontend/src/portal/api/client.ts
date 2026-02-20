/**
 * Real API client — only implements functions that have actual backend endpoints.
 *
 * Backend base URL is configured via VITE_API_URL environment variable:
 *   - Development: Uses Vite proxy (VITE_API_URL not set)
 *   - Production/Vercel: Set VITE_API_URL to full backend URL (e.g., https://api.example.com)
 *
 * Available real endpoints:
 *   POST /api/auth/google              → Google OAuth login
 *   GET  /api/auth/me                  → current user
 *   POST /api/trading-buddy/evaluate   → evaluateTrade
 *   GET  /api/trading-buddy/evaluators → fetchEvaluators
 *   GET  /api/broker/status            → fetchBrokerStatus
 *   GET  /api/broker/trades            → fetchTrades
 *   GET  /api/campaigns                → fetchCampaigns
 *   GET  /api/campaigns/{campaignId}   → fetchCampaignDetail
 *   PUT  /api/campaigns/{id}/context   → saveDecisionContext
 *   GET  /api/campaigns/pnl/{symbol}   → fetchTickerPnl
 *   GET  /api/campaigns/pnl/by-ticker  → fetchTickerPnlByTicker
 *   GET  /api/campaigns/pnl/timeseries → fetchTickerPnlTimeseries
 *   GET  /api/sync-status/{symbol}     → fetchSyncStatus
 *   POST /api/sync/{symbol}            → triggerSync
 *   GET  /api/ohlcv/{symbol}           → fetchOHLCVData
 *   GET  /api/features/{symbol}        → fetchFeatures
 *
 * All other functions are served by the mock layer (see api/index.ts).
 */

import { apiUrl } from '../../config';
import { createLogger } from '../utils/logger';
import type {
  EvaluateRequest,
  EvaluateResponse,
  BrokerStatus,
  BrokerageListResponse,
  BrokerConnectResponse,
  BrokerSyncResponse,
  ConnectionStatusDetail,
  TradeListResponse,
  TradeSummary,
  CampaignSummary,
  CampaignDetail,
  CampaignCheck,
  DecisionContext,
  TickerPnlSummary,
  PnlTimeseries,
  TradingProfile,
  RiskPreferences,
  StrategyDefinition,
  EvaluationControls,
  JournalEntry,
  JournalEntryCreate,
  BehavioralTag,
  SitePrefs,
  OrphanedLegGroup,
} from '../types';

const log = createLogger('ApiClient');

const TOKEN_KEY = 'auth_token';

function getAuthHeaders(): Record<string, string> {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) {
    return { Authorization: `Bearer ${token}` };
  }
  return {};
}

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const method = options?.method ?? 'GET';
  log.debug(`${method} ${url}`);

  const res = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeaders(),
      ...options?.headers,
    },
    ...options,
  });

  if (res.status === 401) {
    // Token expired or invalid — clear auth state and redirect
    log.warn(`${method} ${url} -> 401 Unauthorized, redirecting to login`);
    localStorage.removeItem(TOKEN_KEY);
    window.location.href = '/auth/login';
    throw new Error('Authentication expired');
  }

  if (!res.ok) {
    const body = await res.text().catch(() => '');
    log.error(`${method} ${url} -> ${res.status}`, body || res.statusText);
    throw new Error(`API error ${res.status}: ${body || res.statusText}`);
  }

  log.debug(`${method} ${url} -> ${res.status} OK`);
  return res.json();
}

function get<T>(path: string): Promise<T> {
  return request<T>(apiUrl(path));
}

function post<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(apiUrl(path), { method: 'POST', body: body != null ? JSON.stringify(body) : undefined });
}

function put<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(apiUrl(path), { method: 'PUT', body: body != null ? JSON.stringify(body) : undefined });
}

function del<T>(path: string): Promise<T> {
  return request<T>(apiUrl(path), { method: 'DELETE' });
}

// =============================================================================
// Evaluation — POST /api/trading-buddy/evaluate
// =============================================================================

export async function evaluateTrade(req: EvaluateRequest): Promise<EvaluateResponse> {
  return post<EvaluateResponse>('/api/trading-buddy/evaluate', req);
}

// =============================================================================
// Evaluators — GET /api/trading-buddy/evaluators
// Returns { evaluators: [{ name, class, description }] }
// We extract just the names to match the portal's string[] interface.
// =============================================================================

export async function fetchEvaluators(): Promise<string[]> {
  const res = await get<{ evaluators: { name: string; class: string; description: string }[] }>(
    '/api/trading-buddy/evaluators'
  );
  return res.evaluators.map((e) => e.name);
}

// =============================================================================
// Broker Status — GET /api/broker/status
// Response: { connected: bool, brokerages: string[] }
// =============================================================================

export async function fetchBrokerStatus(): Promise<BrokerStatus> {
  return get<BrokerStatus>('/api/broker/status');
}

// =============================================================================
// Brokerages Catalog — GET /api/broker/brokerages
// =============================================================================

export async function fetchBrokerages(): Promise<BrokerageListResponse> {
  return get<BrokerageListResponse>('/api/broker/brokerages');
}

// =============================================================================
// Broker Connections — GET /api/broker/connections
// =============================================================================

export async function fetchBrokerConnections(): Promise<ConnectionStatusDetail> {
  return get<ConnectionStatusDetail>('/api/broker/connections');
}

// =============================================================================
// Connect Broker — POST /api/broker/connect
// =============================================================================

export async function connectBroker(
  slug?: string,
  redirectUrl?: string,
): Promise<BrokerConnectResponse> {
  return post<BrokerConnectResponse>('/api/broker/connect', {
    broker: slug,
    redirect_url: redirectUrl,
  });
}

// =============================================================================
// Disconnect Broker — DELETE /api/broker/connections/{authorizationId}
// =============================================================================

export async function disconnectBroker(
  authorizationId: string,
): Promise<{ status: string; authorization_id: string }> {
  return del<{ status: string; authorization_id: string }>(
    `/api/broker/connections/${encodeURIComponent(authorizationId)}`,
  );
}

// =============================================================================
// Sync Broker Data — POST /api/broker/sync
// =============================================================================

export async function syncBrokerData(): Promise<BrokerSyncResponse> {
  return post<BrokerSyncResponse>('/api/broker/sync');
}

// =============================================================================
// Chart Data Types
// =============================================================================

export interface SyncStatusEntry {
  symbol: string;
  timeframe: string;
  last_synced_timestamp: string | null;
  first_synced_timestamp: string | null;
  last_sync_at: string | null;
  bars_fetched: number;
  total_bars: number;
  status: string;
  error_message: string | null;
}

export interface SyncResult {
  message: string;
  bars_loaded: number;
  date_range: { start: string | null; end: string | null };
}

export interface OHLCVData {
  timestamps: string[];
  open: number[];
  high: number[];
  low: number[];
  close: number[];
  volume: number[];
}

export interface FeatureData {
  timestamps: string[];
  features: Record<string, number[]>;
  feature_names: string[];
}

// =============================================================================
// Sync Status — GET /api/sync-status/{symbol}
// =============================================================================

export async function fetchSyncStatus(symbol: string): Promise<SyncStatusEntry[]> {
  return get<SyncStatusEntry[]>(`/api/sync-status/${encodeURIComponent(symbol)}`);
}

// =============================================================================
// Trigger Sync — POST /api/sync/{symbol}
// =============================================================================

export async function triggerSync(symbol: string, timeframe?: string): Promise<SyncResult> {
  const params = new URLSearchParams();
  if (timeframe) params.set('timeframe', timeframe);
  const qs = params.toString();
  return post<SyncResult>(`/api/sync/${encodeURIComponent(symbol)}${qs ? `?${qs}` : ''}`);
}

// =============================================================================
// OHLCV Data — GET /api/ohlcv/{symbol}
// =============================================================================

export async function fetchOHLCVData(
  symbol: string,
  timeframe?: string,
  startDate?: string,
  endDate?: string,
): Promise<OHLCVData> {
  const params = new URLSearchParams();
  if (timeframe) params.set('timeframe', timeframe);
  if (startDate) params.set('start_date', startDate);
  if (endDate) params.set('end_date', endDate);
  const qs = params.toString();
  return get<OHLCVData>(`/api/ohlcv/${encodeURIComponent(symbol)}${qs ? `?${qs}` : ''}`);
}

// =============================================================================
// Features — GET /api/features/{symbol}
// =============================================================================

export async function fetchFeatures(
  symbol: string,
  timeframe?: string,
  startDate?: string,
  endDate?: string,
): Promise<FeatureData> {
  const params = new URLSearchParams();
  if (timeframe) params.set('timeframe', timeframe);
  if (startDate) params.set('start_date', startDate);
  if (endDate) params.set('end_date', endDate);
  const qs = params.toString();
  return get<FeatureData>(`/api/features/${encodeURIComponent(symbol)}${qs ? `?${qs}` : ''}`);
}

// =============================================================================
// Trades — GET /api/broker/trades
// Maps broker TradeResponse → portal TradeSummary
// =============================================================================

interface BrokerContextSummary {
  strategy: string | null;
  emotions: string | null;
  hypothesis_snippet: string | null;
}

interface BrokerTradeResponse {
  id: number;
  symbol: string;
  side: string;
  quantity: number;
  price: number;
  fees: number;
  executed_at: string;
  brokerage: string;
  context_summary: BrokerContextSummary | null;
}

interface BrokerTradeListResponse {
  trades: BrokerTradeResponse[];
  total: number;
  page: number;
  limit: number;
}

export async function fetchTrades(params: {
  source?: string;
  flagged?: boolean;
  symbol?: string;
  status?: string;
  uncategorized?: boolean;
  sort?: string;
  page?: number;
  limit?: number;
} = {}): Promise<TradeListResponse> {
  // Map portal sort fields to backend column names
  const SORT_MAP: Record<string, string> = { entry_time: 'executed_at', symbol: 'symbol' };
  function mapSort(sort?: string): string | undefined {
    if (!sort) return undefined;
    const desc = sort.startsWith('-');
    const field = desc ? sort.slice(1) : sort;
    const mapped = SORT_MAP[field] ?? field;
    return desc ? `-${mapped}` : mapped;
  }

  const qs = new URLSearchParams();
  // user_id is extracted from JWT token by the auth middleware
  if (params.symbol) qs.set('symbol', params.symbol);
  if (params.uncategorized) qs.set('uncategorized', 'true');
  const sortVal = mapSort(params.sort);
  if (sortVal) qs.set('sort', sortVal);
  if (params.page) qs.set('page', String(params.page));
  if (params.limit) qs.set('limit', String(params.limit));

  const res = await get<BrokerTradeListResponse>(`/api/broker/trades?${qs.toString()}`);

  const trades: TradeSummary[] = res.trades.map((t) => ({
    id: String(t.id),
    symbol: t.symbol,
    direction: t.side === 'buy' ? 'long' as const : 'short' as const,
    entry_price: t.price,
    exit_price: null,
    quantity: t.quantity,
    entry_time: t.executed_at,
    exit_time: null,
    source: 'synced' as const,
    brokerage: t.brokerage,
    is_flagged: false,
    flag_count: 0,
    status: 'closed' as const,
    timeframe: '',
    context_summary: t.context_summary,
  }));

  return { trades, total: res.total, page: res.page, limit: res.limit };
}

// =============================================================================
// Campaigns — GET /api/campaigns
// =============================================================================

/**
 * Backend returns campaign detail with fills mapped to "legs".
 * Evaluation bundles are not yet implemented server-side — the frontend
 * provides empty defaults so the UI renders gracefully.
 */

interface BackendCampaignDetail {
  campaign: CampaignDetail['campaign'];
  legs: CampaignDetail['legs'];
  contextsByLeg: Record<string, DecisionContext | undefined>;
  checksByLeg: Record<string, CampaignCheck[]>;
}

export async function fetchCampaigns(
  params: { symbol?: string; status?: string } = {},
): Promise<CampaignSummary[]> {
  const qs = new URLSearchParams();
  if (params.symbol) qs.set('symbol', params.symbol);
  if (params.status) qs.set('status', params.status);
  const qsStr = qs.toString();
  return get<CampaignSummary[]>(`/api/campaigns${qsStr ? `?${qsStr}` : ''}`);
}

// =============================================================================
// Uncategorized Fills Count - GET /api/campaigns/uncategorized-count
// Returns count of trade fills not yet processed into campaigns
// =============================================================================

interface UncategorizedCountResponse {
  count: number;
}

export async function fetchUncategorizedCount(): Promise<number> {
  const res = await get<UncategorizedCountResponse>('/api/campaigns/uncategorized-count');
  return res.count;
}

// =============================================================================
// Delete Campaign — DELETE /api/campaigns/{campaignId}
// =============================================================================

export interface DeleteCampaignResponse {
  deleted: boolean;
  legs_orphaned: number;
  contexts_updated: number;
}

export async function deleteCampaign(campaignId: string): Promise<DeleteCampaignResponse> {
  return del<DeleteCampaignResponse>(`/api/campaigns/${encodeURIComponent(campaignId)}`);
}

// =============================================================================
// Orphaned Legs — GET /api/campaigns/orphaned-legs
// =============================================================================

export async function fetchOrphanedLegs(): Promise<OrphanedLegGroup[]> {
  return get<OrphanedLegGroup[]>('/api/campaigns/orphaned-legs');
}

export async function fetchCampaignDetail(campaignId: string): Promise<CampaignDetail> {
  const raw = await get<BackendCampaignDetail>(`/api/campaigns/${encodeURIComponent(campaignId)}`);

  // Backend does not yet return evaluation bundles. Provide empty defaults
  // so the UI can render the campaign detail page without errors.
  const emptyBundle = {
    bundleId: `backend-${campaignId}`,
    evalScope: 'campaign' as const,
    overallLabel: 'mixed' as const,
    dimensions: [],
  };

  return {
    campaign: raw.campaign,
    legs: raw.legs,
    evaluationCampaign: emptyBundle,
    evaluationByLeg: {},
    contextsByLeg: raw.contextsByLeg ?? {},
    checksByLeg: raw.checksByLeg ?? {},
  };
}

export async function saveDecisionContext(context: DecisionContext): Promise<DecisionContext> {
  // In the new schema, each "leg" is actually a fill. The legId IS the fill_id.
  // We save context per-fill using the fill context endpoint.
  const fillId = context.legId;
  if (!fillId) throw new Error('legId (fill ID) is required to save context');

  const body = {
    contextType: context.contextType,
    strategyName: context.strategyTags?.[0] ?? null,
    hypothesis: context.hypothesis,
    exitIntent: context.exitIntent,
    feelingsThen: context.feelingsThen,
    feelingsNow: context.feelingsNow,
    notes: context.notes,
  };

  const res = await put<{
    contextId: string;
    fillId: string;
    contextType: string;
    strategyName?: string;
    hypothesis?: string;
    exitIntent?: string;
    feelingsThen?: { chips: string[]; intensity?: number; note?: string };
    feelingsNow?: { chips: string[]; intensity?: number; note?: string };
    notes?: string;
    updatedAt: string;
  }>(`/api/campaigns/fills/${encodeURIComponent(fillId)}/context`, body);

  return {
    contextId: res.contextId,
    scope: context.scope,
    campaignId: context.campaignId,
    legId: res.fillId,
    contextType: res.contextType as DecisionContext['contextType'],
    strategyTags: res.strategyName ? [res.strategyName] : [],
    hypothesis: res.hypothesis,
    exitIntent: res.exitIntent as DecisionContext['exitIntent'],
    feelingsThen: res.feelingsThen,
    feelingsNow: res.feelingsNow,
    notes: res.notes,
    updatedAt: res.updatedAt,
  };
}

// =============================================================================
// Campaign OHLCV — GET /api/ohlcv/{symbol} with date range
// Convenience wrapper that accepts ms timestamps for campaign chart data.
// =============================================================================

export async function fetchCampaignOHLCVData(
  symbol: string,
  rangeStartMs: number,
  rangeEndMs: number,
): Promise<OHLCVData> {
  const startDate = new Date(rangeStartMs).toISOString().split('T')[0];
  const endDate = new Date(rangeEndMs).toISOString().split('T')[0];
  return fetchOHLCVData(symbol, undefined, startDate, endDate);
}

// =============================================================================
// Ticker P&L — GET /api/campaigns/pnl/{symbol}
// Returns P&L summary for a single ticker symbol
// =============================================================================

export async function fetchTickerPnl(symbol: string): Promise<TickerPnlSummary> {
  const res = await get<TickerPnlSummary>(
    `/api/campaigns/pnl/${encodeURIComponent(symbol)}`
  );

  return {
    symbol: res.symbol,
    total_pnl: res.total_pnl,
    total_pnl_pct: res.total_pnl_pct,
    trade_count: res.trade_count,
    closed_count: res.closed_count,
    first_entry_time: res.first_entry_time ?? new Date().toISOString(),
  };
}

// =============================================================================
// Ticker P&L Timeseries — GET /api/campaigns/pnl/timeseries
// Returns cumulative P&L over time for charting
// =============================================================================

interface PnlTimeseriesPoint {
  timestamp: string;
  realized_pnl: number;
  cumulative_pnl: number;
  trade_count: number;
}

interface PnlTimeseriesBackendResponse {
  symbol: string | null;
  points: PnlTimeseriesPoint[];
  total_pnl: number;
  period_start: string | null;
  period_end: string | null;
}

/**
 * Fetch P&L timeseries from backend and interpolate to match OHLCV timestamps.
 *
 * The backend returns daily realized P&L points. This function maps those
 * onto the provided OHLCV timestamps by carrying forward the cumulative P&L
 * from the most recent trade date at or before each OHLCV timestamp.
 *
 * @param symbol - Ticker symbol
 * @param ohlcvTimestamps - Array of OHLCV bar timestamps (ISO strings)
 * @param _ohlcvClose - Array of close prices (unused, kept for API compatibility)
 */
export async function fetchTickerPnlTimeseries(
  symbol: string,
  ohlcvTimestamps: string[],
  _ohlcvClose: number[],
): Promise<PnlTimeseries> {
  // Determine date range from OHLCV timestamps
  if (ohlcvTimestamps.length === 0) {
    return { timestamps: [], cumulative_pnl: [] };
  }

  const startDate = ohlcvTimestamps[0].split('T')[0];
  const endDate = ohlcvTimestamps[ohlcvTimestamps.length - 1].split('T')[0];

  // Fetch P&L timeseries from backend
  const params = new URLSearchParams();
  params.set('symbol', symbol);
  params.set('start_date', startDate);
  params.set('end_date', endDate);
  params.set('granularity', 'day');

  const res = await get<PnlTimeseriesBackendResponse>(
    `/api/campaigns/pnl/timeseries?${params.toString()}`
  );

  // Build a map of date -> cumulative P&L for fast lookup
  const pnlByDate = new Map<string, number>();
  for (const point of res.points) {
    // Extract date from timestamp (YYYY-MM-DD)
    const date = point.timestamp.split('T')[0];
    pnlByDate.set(date, point.cumulative_pnl);
  }

  // Interpolate: for each OHLCV timestamp, find the cumulative P&L
  // from the most recent trade date at or before that timestamp
  const cumulative_pnl: number[] = [];

  // Sort backend dates for binary search (already sorted from backend)
  const sortedDates = Array.from(pnlByDate.keys()).sort();

  for (const ts of ohlcvTimestamps) {
    const tsDate = ts.split('T')[0];

    // Find the latest date <= tsDate
    let pnl = 0;
    for (let i = sortedDates.length - 1; i >= 0; i--) {
      if (sortedDates[i] <= tsDate) {
        pnl = pnlByDate.get(sortedDates[i]) ?? 0;
        break;
      }
    }

    cumulative_pnl.push(pnl);
  }

  return {
    timestamps: ohlcvTimestamps,
    cumulative_pnl,
  };
}

// =============================================================================
// Aggregate P&L Timeseries — GET /api/campaigns/pnl/timeseries (no symbol)
// Returns daily P&L points across all tickers for the Dashboard equity curve.
// =============================================================================

export interface DailyPnlPoint {
  date: string;
  realizedPnl: number;
  cumulativePnl: number;
  tradeCount: number;
}

export async function fetchAggregatePnlTimeseries(): Promise<DailyPnlPoint[]> {
  const res = await get<PnlTimeseriesBackendResponse>(
    '/api/campaigns/pnl/timeseries?granularity=day'
  );

  return res.points.map((p) => ({
    date: p.timestamp.split('T')[0],
    realizedPnl: p.realized_pnl,
    cumulativePnl: p.cumulative_pnl,
    tradeCount: p.trade_count,
  }));
}

// =============================================================================
// Trading Profile — GET/PUT /api/user/profile
// =============================================================================

export async function fetchTradingProfile(): Promise<TradingProfile> {
  return get<TradingProfile>('/api/user/profile');
}

export async function updateTradingProfile(profile: TradingProfile): Promise<TradingProfile> {
  return put<TradingProfile>('/api/user/profile', profile);
}

// =============================================================================
// Risk Preferences — GET/PUT /api/user/risk-preferences
// =============================================================================

export async function fetchRiskPreferences(): Promise<RiskPreferences> {
  return get<RiskPreferences>('/api/user/risk-preferences');
}

export async function updateRiskPreferences(prefs: RiskPreferences): Promise<RiskPreferences> {
  return put<RiskPreferences>('/api/user/risk-preferences', prefs);
}

// =============================================================================
// Strategies — GET/POST/PUT /api/user/strategies
// =============================================================================

export async function fetchStrategies(): Promise<StrategyDefinition[]> {
  return get<StrategyDefinition[]>('/api/user/strategies');
}

export async function createStrategy(strategy: Omit<StrategyDefinition, 'id'>): Promise<StrategyDefinition> {
  return post<StrategyDefinition>('/api/user/strategies', strategy);
}

export async function updateStrategy(id: number, updates: Partial<StrategyDefinition>): Promise<StrategyDefinition> {
  return put<StrategyDefinition>(`/api/user/strategies/${id}`, updates);
}

// =============================================================================
// Evaluation Controls — GET/PUT /api/user/evaluation-controls
// =============================================================================

export async function fetchEvaluationControls(): Promise<EvaluationControls> {
  return get<EvaluationControls>('/api/user/evaluation-controls');
}

export async function updateEvaluationControls(controls: EvaluationControls): Promise<EvaluationControls> {
  return put<EvaluationControls>('/api/user/evaluation-controls', controls);
}

// =============================================================================
// Journal — GET/POST/PUT /api/journal/entries, GET /api/journal/tags
// =============================================================================

export async function fetchJournalEntries(): Promise<JournalEntry[]> {
  return get<JournalEntry[]>('/api/journal/entries');
}

export async function createJournalEntry(entry: JournalEntryCreate): Promise<JournalEntry> {
  return post<JournalEntry>('/api/journal/entries', entry);
}

export async function updateJournalEntry(entryId: string, updates: Partial<JournalEntryCreate>): Promise<JournalEntry> {
  return put<JournalEntry>(`/api/journal/entries/${encodeURIComponent(entryId)}`, updates);
}

export async function fetchBehavioralTags(): Promise<BehavioralTag[]> {
  return get<BehavioralTag[]>('/api/journal/tags');
}

// =============================================================================
// Site Preferences — GET/PUT /api/user/site-prefs
// =============================================================================

export async function fetchSitePrefs(): Promise<SitePrefs> {
  return get<SitePrefs>('/api/user/site-prefs');
}

export async function updateSitePrefs(prefs: Partial<SitePrefs>): Promise<SitePrefs> {
  return put<SitePrefs>('/api/user/site-prefs', prefs);
}

// =============================================================================
// Bulk Strategy Update — POST /api/broker/fills/bulk-update-strategy
// =============================================================================

export interface BulkUpdateStrategyRequest {
  fill_ids: number[];
  strategy_id: number | null;
}

export interface BulkUpdateStrategyResponse {
  updated_count: number;
  skipped_count: number;
}

export async function bulkUpdateStrategy(
  req: BulkUpdateStrategyRequest,
): Promise<BulkUpdateStrategyResponse> {
  return post<BulkUpdateStrategyResponse>('/api/broker/fills/bulk-update-strategy', req);
}

// =============================================================================
// Bulk Leg Strategy Update — POST /api/campaigns/legs/bulk-update-strategy
// =============================================================================

export interface BulkUpdateLegStrategyRequest {
  leg_ids: number[];
  strategy_id: number | null;
}

export interface BulkUpdateLegStrategyResponse {
  updated_count: number;
  skipped_count: number;
}

export async function bulkUpdateLegStrategy(
  req: BulkUpdateLegStrategyRequest,
): Promise<BulkUpdateLegStrategyResponse> {
  return post<BulkUpdateLegStrategyResponse>('/api/campaigns/legs/bulk-update-strategy', req);
}

// =============================================================================
// Fill Context — GET/PUT /api/broker/fills/{fillId}/context
// =============================================================================

import type {
  FillContextDetail,
  SaveFillContextRequest,
  AgentStrategy,
  AgentSummary,
  AgentCreateRequest,
  AgentUpdateRequest,
  AgentOrder,
  AgentActivity,
} from '../types';

export async function fetchFillContext(fillId: string): Promise<FillContextDetail> {
  return get<FillContextDetail>(`/api/broker/fills/${encodeURIComponent(fillId)}/context`);
}

export async function saveFillContext(
  fillId: string,
  context: SaveFillContextRequest
): Promise<FillContextDetail> {
  return put<FillContextDetail>(`/api/broker/fills/${encodeURIComponent(fillId)}/context`, context);
}

// =============================================================================
// Strategy Probe — GET /api/strategy-probe/{symbol}
// Returns weekly strategy performance rankings for a given symbol
// =============================================================================

export interface ThemeRanking {
  theme: string;
  num_trades: number;
  num_profitable: number;
  num_unprofitable: number;
  num_long: number;
  num_short: number;
  avg_pnl_per_trade: number;
  weighted_avg_pnl: number;
  rank: number;
  top_strategy_name: string;
}

export interface WeekPerformance {
  week_start: string;
  week_end: string;
  themes: ThemeRanking[];
}

export interface StrategyProbeResponse {
  symbol: string;
  weeks: WeekPerformance[];
  available_timeframes: string[];
}

export async function fetchStrategyProbe(
  symbol: string,
  startDate?: string,
  endDate?: string,
  timeframe?: string,
  direction?: string,
): Promise<StrategyProbeResponse> {
  const params = new URLSearchParams();
  if (startDate) params.set('start_date', startDate);
  if (endDate) params.set('end_date', endDate);
  if (timeframe) params.set('timeframe', timeframe);
  if (direction) params.set('direction', direction);
  const qs = params.toString();
  return get<StrategyProbeResponse>(
    `/api/strategy-probe/${encodeURIComponent(symbol)}${qs ? `?${qs}` : ''}`,
  );
}

// =============================================================================
// Theme Strategies — GET /api/strategy-probe/strategies/{strategy_type}
// Returns all strategies belonging to a theme with their details
// =============================================================================

export interface ThemeStrategyDetail {
  display_name: string;
  name: string;
  philosophy: string;
  direction: string;
  details: Record<string, unknown>;
}

export interface ThemeStrategiesResponse {
  strategy_type: string;
  strategies: ThemeStrategyDetail[];
}

export async function fetchThemeStrategies(
  strategyType: string,
): Promise<ThemeStrategiesResponse> {
  return get<ThemeStrategiesResponse>(
    `/api/strategy-probe/strategies/${encodeURIComponent(strategyType)}`,
  );
}

export async function fetchAllProbeStrategies(): Promise<ThemeStrategiesResponse> {
  return get<ThemeStrategiesResponse>('/api/strategy-probe/strategies');
}

// =============================================================================
// Top Strategies — GET /api/strategy-probe/top-strategies/{symbol}/{strategy_type}
// Returns top 3 strategies for a theme within a specific week
// =============================================================================

export interface TopStrategyDetail {
  display_name: string;
  name: string;
  philosophy: string;
  direction: string;
  details: Record<string, unknown>;
  num_trades: number;
  num_profitable: number;
  num_unprofitable: number;
  weighted_avg_pnl: number;
  avg_pnl_per_trade: number;
}

export interface TopStrategiesResponse {
  strategy_type: string;
  week_start: string;
  week_end: string;
  strategies: TopStrategyDetail[];
}

export async function fetchTopStrategies(
  symbol: string,
  strategyType: string,
  weekStart: string,
  weekEnd: string,
  timeframe?: string,
): Promise<TopStrategiesResponse> {
  const params = new URLSearchParams();
  params.set('week_start', weekStart);
  params.set('week_end', weekEnd);
  if (timeframe) params.set('timeframe', timeframe);
  return get<TopStrategiesResponse>(
    `/api/strategy-probe/top-strategies/${encodeURIComponent(symbol)}/${encodeURIComponent(strategyType)}?${params.toString()}`,
  );
}

// =============================================================================
// Trading Agents — Strategies
// =============================================================================

export async function fetchAgentStrategies(): Promise<AgentStrategy[]> {
  return get<AgentStrategy[]>('/api/agents/strategies');
}

export async function fetchAgentStrategy(strategyId: number): Promise<AgentStrategy> {
  return get<AgentStrategy>(`/api/agents/strategies/${strategyId}`);
}

export async function createAgentStrategy(data: Partial<AgentStrategy>): Promise<AgentStrategy> {
  return post<AgentStrategy>('/api/agents/strategies', data);
}

export async function cloneAgentStrategy(strategyId: number, newName: string): Promise<AgentStrategy> {
  return post<AgentStrategy>(`/api/agents/strategies/${strategyId}/clone`, { new_name: newName });
}

export async function updateAgentStrategy(strategyId: number, data: Partial<AgentStrategy>): Promise<AgentStrategy> {
  return put<AgentStrategy>(`/api/agents/strategies/${strategyId}`, data);
}

// =============================================================================
// Trading Agents — Agent CRUD
// =============================================================================

export async function fetchAgents(): Promise<AgentSummary[]> {
  return get<AgentSummary[]>('/api/agents');
}

export async function fetchAgent(agentId: number): Promise<AgentSummary> {
  return get<AgentSummary>(`/api/agents/${agentId}`);
}

export async function createAgent(data: AgentCreateRequest): Promise<AgentSummary> {
  return post<AgentSummary>('/api/agents', data);
}

export async function updateAgent(agentId: number, data: AgentUpdateRequest): Promise<AgentSummary> {
  return put<AgentSummary>(`/api/agents/${agentId}`, data);
}

export async function deleteAgent(agentId: number): Promise<void> {
  return del<void>(`/api/agents/${agentId}`);
}

// =============================================================================
// Trading Agents — Lifecycle
// =============================================================================

export async function startAgent(agentId: number): Promise<AgentSummary> {
  return post<AgentSummary>(`/api/agents/${agentId}/start`);
}

export async function pauseAgent(agentId: number): Promise<AgentSummary> {
  return post<AgentSummary>(`/api/agents/${agentId}/pause`);
}

export async function stopAgent(agentId: number): Promise<AgentSummary> {
  return post<AgentSummary>(`/api/agents/${agentId}/stop`);
}

// =============================================================================
// Trading Agents — Orders & Activity
// =============================================================================

export async function fetchAgentOrders(agentId: number): Promise<AgentOrder[]> {
  return get<AgentOrder[]>(`/api/agents/${agentId}/orders`);
}

export async function fetchAgentActivity(agentId: number): Promise<AgentActivity[]> {
  return get<AgentActivity[]>(`/api/agents/${agentId}/activity`);
}
