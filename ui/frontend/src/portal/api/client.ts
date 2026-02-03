/**
 * Real API client — only implements functions that have actual backend endpoints.
 *
 * Backend base URL is proxied via Vite config: /api/* → http://localhost:8000/api/*
 *
 * Available real endpoints:
 *   POST /api/trading-buddy/evaluate       → evaluateTrade
 *   GET  /api/trading-buddy/evaluators     → fetchEvaluators
 *   GET  /api/broker/status?user_id=       → fetchBrokerStatus
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
