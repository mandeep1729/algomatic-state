/**
 * Real API client — only implements functions that have actual backend endpoints.
 *
 * Backend base URL is proxied via Vite config: /api/* → http://localhost:8000/api/*
 *
 * Available real endpoints:
 *   POST /api/auth/google            → Google OAuth login
 *   GET  /api/auth/me                → current user
 *   POST /api/trading-buddy/evaluate → evaluateTrade
 *   GET  /api/trading-buddy/evaluators → fetchEvaluators
 *   GET  /api/broker/status           → fetchBrokerStatus
 *   GET  /api/broker/trades           → fetchTrades
 *   GET  /api/campaigns/{campaignId}  → fetchTradeDetail
 *   GET  /api/sync-status/{symbol}    → fetchSyncStatus
 *   POST /api/sync/{symbol}           → triggerSync
 *   GET  /api/ohlcv/{symbol}          → fetchOHLCVData
 *   GET  /api/features/{symbol}       → fetchFeatures
 *
 * All other functions are served by the mock layer (see api/index.ts).
 */

import type {
  EvaluateRequest,
  EvaluateResponse,
  BrokerStatus,
  TradeListResponse,
  TradeSummary,
  TradeDetail,
  TradeDirection,
  TradeSource,
  TradeStatus,
} from '../types';

const TOKEN_KEY = 'auth_token';

function getAuthHeaders(): Record<string, string> {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) {
    return { Authorization: `Bearer ${token}` };
  }
  return {};
}

async function request<T>(url: string, options?: RequestInit): Promise<T> {
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
    localStorage.removeItem(TOKEN_KEY);
    window.location.href = '/auth/login';
    throw new Error('Authentication expired');
  }

  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(`API error ${res.status}: ${body || res.statusText}`);
  }
  return res.json();
}

function get<T>(url: string): Promise<T> {
  return request<T>(url);
}

function post<T>(url: string, body?: unknown): Promise<T> {
  return request<T>(url, { method: 'POST', body: body != null ? JSON.stringify(body) : undefined });
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

interface BrokerTradeResponse {
  id: number;
  symbol: string;
  side: string;
  quantity: number;
  price: number;
  fees: number;
  executed_at: string;
  brokerage: string;
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
  }));

  return { trades, total: res.total, page: res.page, limit: res.limit };
}

// =============================================================================
// Campaign Detail — GET /api/campaigns/{campaignId}
// Maps backend CampaignDetailResponse → portal TradeDetail
// =============================================================================

interface CampaignLegResponse {
  id: number;
  leg_type: string;
  side: string;
  quantity: number;
  avg_price: number | null;
  started_at: string;
  ended_at: string | null;
  fill_count: number;
  notes: string | null;
  fills: { fill_id: number; allocated_qty: number | null }[];
}

interface CampaignDetailResponse {
  id: number;
  symbol: string;
  direction: string;
  status: string;
  opened_at: string | null;
  closed_at: string | null;
  holding_period_sec: number | null;
  qty_opened: number | null;
  qty_closed: number | null;
  avg_open_price: number | null;
  avg_close_price: number | null;
  realized_pnl: number | null;
  return_pct: number | null;
  r_multiple: number | null;
  legs: CampaignLegResponse[];
  tags: Record<string, unknown>;
  notes: string | null;
}

export async function fetchTradeDetail(campaignId: string): Promise<TradeDetail> {
  const res = await get<CampaignDetailResponse>(
    `/api/campaigns/${encodeURIComponent(campaignId)}`
  );

  // Map campaign direction to TradeDirection
  const direction: TradeDirection = res.direction === 'long' ? 'long' : 'short';

  // Map campaign status to TradeStatus
  const status: TradeStatus = res.status === 'open' ? 'open' : 'closed';

  // Extract tags as string array from the tags object
  const tags: string[] = res.tags && typeof res.tags === 'object'
    ? Object.keys(res.tags)
    : [];

  // Get entry and exit times from legs or campaign timestamps
  const entryTime = res.opened_at ?? (res.legs.length > 0 ? res.legs[0].started_at : '');
  const exitTime = res.closed_at ?? (res.status === 'closed' && res.legs.length > 0
    ? res.legs[res.legs.length - 1].ended_at
    : null);

  // Sum quantities from legs
  const quantity = res.qty_opened ?? res.legs.reduce((sum, leg) => sum + leg.quantity, 0);

  return {
    id: String(res.id),
    symbol: res.symbol,
    direction,
    entry_price: res.avg_open_price ?? 0,
    exit_price: res.avg_close_price,
    quantity,
    entry_time: entryTime,
    exit_time: exitTime,
    source: 'synced' as TradeSource,
    brokerage: null,
    is_flagged: false,
    flag_count: 0,
    status,
    timeframe: '',
    stop_loss: null,
    profit_target: null,
    risk_reward_ratio: res.r_multiple,
    pnl: res.realized_pnl,
    pnl_pct: res.return_pct,
    evaluation: null,
    notes: res.notes,
    tags,
  };
}
