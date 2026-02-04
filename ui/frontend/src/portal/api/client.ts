/**
 * Real API client — only implements functions that have actual backend endpoints.
 *
 * Backend base URL is proxied via Vite config: /api/* → http://localhost:8000/api/*
 *
 * Available real endpoints:
 *   POST /api/trading-buddy/evaluate       → evaluateTrade
 *   GET  /api/trading-buddy/evaluators     → fetchEvaluators
 *   GET  /api/broker/status?user_id=       → fetchBrokerStatus
 *   GET  /api/sync-status/{symbol}         → fetchSyncStatus
 *   POST /api/sync/{symbol}               → triggerSync
 *   GET  /api/ohlcv/{symbol}              → fetchOHLCVData
 *   GET  /api/features/{symbol}           → fetchFeatures
 *
 * All other functions are served by the mock layer (see api/index.ts).
 */

import type {
  EvaluateRequest,
  EvaluateResponse,
  BrokerStatus,
} from '../types';

// Hardcoded user ID until auth is implemented
const USER_ID = 1;

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  });
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
// Broker Status — GET /api/broker/status?user_id=
// Response: { connected: bool, brokerages: string[] }
// =============================================================================

export async function fetchBrokerStatus(): Promise<BrokerStatus> {
  return get<BrokerStatus>(`/api/broker/status?user_id=${USER_ID}`);
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
