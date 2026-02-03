/**
 * Real API client — mirrors the function signatures of mockApi.ts.
 *
 * Backend base URL is proxied via Vite config: /api/* → http://localhost:8000/api/*
 *
 * Endpoint mapping:
 *   Trading Buddy routes  → /api/trading-buddy/*
 *   Broker routes         → /api/broker/*
 *   General data routes   → /api/*
 */

import type {
  User,
  TradingProfile,
  RiskPreferences,
  TradeListResponse,
  TradeDetail,
  TradeSummary,
  EvaluateRequest,
  EvaluateResponse,
  InsightsSummary,
  RegimeInsight,
  TimingInsight,
  BehavioralInsight,
  RiskInsight,
  StrategyDriftInsight,
  JournalEntry,
  JournalEntryCreate,
  BehavioralTag,
  StrategyDefinition,
  EvaluationControls,
  OnboardingStatus,
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

function put<T>(url: string, body: unknown): Promise<T> {
  return request<T>(url, { method: 'PUT', body: JSON.stringify(body) });
}

function patch<T>(url: string, body: unknown): Promise<T> {
  return request<T>(url, { method: 'PATCH', body: JSON.stringify(body) });
}

// =============================================================================
// User / Auth
// =============================================================================

export async function fetchCurrentUser(): Promise<User> {
  return get<User>(`/api/trading-buddy/user/${USER_ID}`);
}

export async function fetchTradingProfile(): Promise<TradingProfile> {
  return get<TradingProfile>(`/api/trading-buddy/user/${USER_ID}/profile`);
}

export async function updateTradingProfile(profile: TradingProfile): Promise<TradingProfile> {
  return put<TradingProfile>(`/api/trading-buddy/user/${USER_ID}/profile`, profile);
}

export async function fetchRiskPreferences(): Promise<RiskPreferences> {
  return get<RiskPreferences>(`/api/trading-buddy/user/${USER_ID}/risk-preferences`);
}

export async function updateRiskPreferences(prefs: RiskPreferences): Promise<RiskPreferences> {
  return put<RiskPreferences>(`/api/trading-buddy/user/${USER_ID}/risk-preferences`, prefs);
}

// =============================================================================
// Trades
// =============================================================================

export async function fetchTrades(params: {
  source?: string;
  flagged?: boolean;
  symbol?: string;
  status?: string;
  sort?: string;
  page?: number;
  limit?: number;
} = {}): Promise<TradeListResponse> {
  const searchParams = new URLSearchParams();
  if (params.source) searchParams.set('source', params.source);
  if (params.flagged !== undefined) searchParams.set('flagged', String(params.flagged));
  if (params.symbol) searchParams.set('symbol', params.symbol);
  if (params.status) searchParams.set('status', params.status);
  if (params.sort) searchParams.set('sort', params.sort);
  if (params.page) searchParams.set('page', String(params.page));
  if (params.limit) searchParams.set('limit', String(params.limit));
  const qs = searchParams.toString();
  return get<TradeListResponse>(`/api/trading-buddy/trades${qs ? `?${qs}` : ''}`);
}

export async function fetchTradeDetail(tradeId: string): Promise<TradeDetail> {
  return get<TradeDetail>(`/api/trading-buddy/trades/${tradeId}`);
}

export async function createManualTrade(trade: Omit<TradeSummary, 'id' | 'is_flagged' | 'flag_count'>): Promise<TradeDetail> {
  return post<TradeDetail>('/api/trading-buddy/trades', trade);
}

// =============================================================================
// Evaluation
// =============================================================================

export async function evaluateTrade(request: EvaluateRequest): Promise<EvaluateResponse> {
  return post<EvaluateResponse>('/api/trading-buddy/evaluate', request);
}

export async function fetchEvaluators(): Promise<string[]> {
  return get<string[]>('/api/trading-buddy/evaluators');
}

// =============================================================================
// Insights
// =============================================================================

export async function fetchInsightsSummary(): Promise<InsightsSummary> {
  return get<InsightsSummary>(`/api/trading-buddy/insights/summary?user_id=${USER_ID}`);
}

export async function fetchRegimeInsights(): Promise<RegimeInsight[]> {
  return get<RegimeInsight[]>(`/api/trading-buddy/insights/regimes?user_id=${USER_ID}`);
}

export async function fetchTimingInsights(): Promise<TimingInsight[]> {
  return get<TimingInsight[]>(`/api/trading-buddy/insights/timing?user_id=${USER_ID}`);
}

export async function fetchBehavioralInsights(): Promise<BehavioralInsight[]> {
  return get<BehavioralInsight[]>(`/api/trading-buddy/insights/behavioral?user_id=${USER_ID}`);
}

export async function fetchRiskInsights(): Promise<RiskInsight[]> {
  return get<RiskInsight[]>(`/api/trading-buddy/insights/risk?user_id=${USER_ID}`);
}

export async function fetchStrategyDriftInsights(): Promise<StrategyDriftInsight[]> {
  return get<StrategyDriftInsight[]>(`/api/trading-buddy/insights/strategy-drift?user_id=${USER_ID}`);
}

// =============================================================================
// Journal
// =============================================================================

export async function fetchJournalEntries(): Promise<JournalEntry[]> {
  return get<JournalEntry[]>(`/api/trading-buddy/journal?user_id=${USER_ID}`);
}

export async function createJournalEntry(entry: JournalEntryCreate): Promise<JournalEntry> {
  return post<JournalEntry>(`/api/trading-buddy/journal?user_id=${USER_ID}`, entry);
}

export async function updateJournalEntry(entryId: string, updates: Partial<JournalEntryCreate>): Promise<JournalEntry> {
  return patch<JournalEntry>(`/api/trading-buddy/journal/${entryId}`, updates);
}

export async function fetchBehavioralTags(): Promise<BehavioralTag[]> {
  return get<BehavioralTag[]>('/api/trading-buddy/behavioral-tags');
}

// =============================================================================
// Strategies / Settings
// =============================================================================

export async function fetchStrategies(): Promise<StrategyDefinition[]> {
  return get<StrategyDefinition[]>(`/api/trading-buddy/strategies?user_id=${USER_ID}`);
}

export async function createStrategy(strategy: Omit<StrategyDefinition, 'id'>): Promise<StrategyDefinition> {
  return post<StrategyDefinition>(`/api/trading-buddy/strategies?user_id=${USER_ID}`, strategy);
}

export async function updateStrategy(id: string, updates: Partial<StrategyDefinition>): Promise<StrategyDefinition> {
  return patch<StrategyDefinition>(`/api/trading-buddy/strategies/${id}`, updates);
}

export async function fetchEvaluationControls(): Promise<EvaluationControls> {
  return get<EvaluationControls>(`/api/trading-buddy/user/${USER_ID}/evaluation-controls`);
}

export async function updateEvaluationControls(controls: EvaluationControls): Promise<EvaluationControls> {
  return put<EvaluationControls>(`/api/trading-buddy/user/${USER_ID}/evaluation-controls`, controls);
}

// =============================================================================
// Onboarding
// =============================================================================

export async function fetchOnboardingStatus(): Promise<OnboardingStatus> {
  return get<OnboardingStatus>(`/api/trading-buddy/user/${USER_ID}/onboarding-status`);
}

// =============================================================================
// Broker
// =============================================================================

export async function fetchBrokerStatus(): Promise<BrokerStatus> {
  return get<BrokerStatus>(`/api/broker/status?user_id=${USER_ID}`);
}
