import { MOCK_TRADES, getTradeSummaries } from './fixtures/trades';
import { MOCK_EVALUATIONS } from './fixtures/evaluations';
import {
  MOCK_INSIGHTS_SUMMARY,
  MOCK_REGIME_INSIGHTS,
  MOCK_TIMING_INSIGHTS,
  MOCK_BEHAVIORAL_INSIGHTS,
  MOCK_RISK_INSIGHTS,
  MOCK_STRATEGY_DRIFT_INSIGHTS,
} from './fixtures/insights';
import { MOCK_JOURNAL_ENTRIES } from './fixtures/journal';
import { MOCK_STRATEGIES, MOCK_EVALUATION_CONTROLS } from './fixtures/strategies';
import { MOCK_BEHAVIORAL_TAGS } from './fixtures/tags';
import { MOCK_ONBOARDING_STATUS } from './fixtures/onboarding';
import { MOCK_USER, MOCK_PROFILE, MOCK_RISK_PREFERENCES } from './mockUser';
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

// Simulate network delay
const delay = (ms = 200) => new Promise<void>(r => setTimeout(r, ms));

// --- User / Auth ---

export async function fetchCurrentUser(): Promise<User> {
  await delay();
  return { ...MOCK_USER };
}

export async function fetchTradingProfile(): Promise<TradingProfile> {
  await delay();
  return { ...MOCK_PROFILE };
}

export async function updateTradingProfile(profile: TradingProfile): Promise<TradingProfile> {
  await delay();
  return { ...profile };
}

export async function fetchRiskPreferences(): Promise<RiskPreferences> {
  await delay();
  return { ...MOCK_RISK_PREFERENCES };
}

export async function updateRiskPreferences(prefs: RiskPreferences): Promise<RiskPreferences> {
  await delay();
  return { ...prefs };
}

// --- Trades ---

export async function fetchTrades(params: {
  source?: string;
  flagged?: boolean;
  symbol?: string;
  status?: string;
  sort?: string;
  page?: number;
  limit?: number;
} = {}): Promise<TradeListResponse> {
  await delay();
  let filtered: TradeSummary[] = getTradeSummaries();

  if (params.source) {
    filtered = filtered.filter(t => t.source === params.source);
  }
  if (params.flagged !== undefined) {
    filtered = filtered.filter(t => t.is_flagged === params.flagged);
  }
  if (params.symbol) {
    const sym = params.symbol.toUpperCase();
    filtered = filtered.filter(t => t.symbol.includes(sym));
  }
  if (params.status) {
    filtered = filtered.filter(t => t.status === params.status);
  }

  // Sort
  const sortField = params.sort ?? '-entry_time';
  const desc = sortField.startsWith('-');
  const field = desc ? sortField.slice(1) : sortField;
  filtered.sort((a, b) => {
    const aVal = a[field as keyof TradeSummary];
    const bVal = b[field as keyof TradeSummary];
    if (aVal == null && bVal == null) return 0;
    if (aVal == null) return 1;
    if (bVal == null) return -1;
    const cmp = aVal < bVal ? -1 : aVal > bVal ? 1 : 0;
    return desc ? -cmp : cmp;
  });

  const page = params.page ?? 1;
  const limit = params.limit ?? 20;
  const start = (page - 1) * limit;

  return {
    trades: filtered.slice(start, start + limit),
    total: filtered.length,
    page,
    limit,
  };
}

export async function fetchTradeDetail(tradeId: string): Promise<TradeDetail> {
  await delay();
  const trade = MOCK_TRADES.find(t => t.id === tradeId);
  if (!trade) throw new Error(`Trade ${tradeId} not found`);

  const evaluation = MOCK_EVALUATIONS[tradeId] ?? null;
  return { ...trade, evaluation };
}

export async function createManualTrade(trade: Omit<TradeSummary, 'id' | 'is_flagged' | 'flag_count'>): Promise<TradeDetail> {
  await delay();
  const newTrade: TradeDetail = {
    ...trade,
    id: `trade-${Date.now()}`,
    is_flagged: false,
    flag_count: 0,
    stop_loss: null,
    profit_target: null,
    risk_reward_ratio: null,
    pnl: null,
    pnl_pct: null,
    evaluation: null,
    notes: null,
    tags: [],
  };
  return newTrade;
}

// --- Evaluation ---

export async function evaluateTrade(request: EvaluateRequest): Promise<EvaluateResponse> {
  await delay(500);
  // Return a mock evaluation for any proposed trade
  const intent = request.intent;
  const rr = (intent.profit_target - intent.entry_price) / (intent.entry_price - intent.stop_loss);

  return {
    intent: {
      intent_id: Date.now(),
      symbol: intent.symbol,
      direction: intent.direction,
      timeframe: intent.timeframe,
      entry_price: intent.entry_price,
      stop_loss: intent.stop_loss,
      profit_target: intent.profit_target,
      position_size: intent.position_size ?? null,
      position_value: intent.position_value ?? null,
      rationale: intent.rationale ?? null,
      status: 'evaluated',
      risk_reward_ratio: Math.round(rr * 100) / 100,
      total_risk: null,
      created_at: new Date().toISOString(),
    },
    evaluation: {
      score: 65,
      summary: 'Trade has acceptable risk parameters. Regime is neutral — no strong conviction either way.',
      has_blockers: false,
      top_issues: [
        {
          evaluator: 'regime_fit',
          code: 'REGIME_NEUTRAL',
          severity: 'info',
          title: 'Neutral market regime',
          message: 'Current regime is consolidation. No strong directional bias to support this trade.',
          evidence: [
            { metric_name: 'regime_label', value: 1, threshold: null, comparison: null, unit: null },
          ],
        },
      ],
      all_items: [
        {
          evaluator: 'regime_fit',
          code: 'REGIME_NEUTRAL',
          severity: 'info',
          title: 'Neutral market regime',
          message: 'Current regime is consolidation. No strong directional bias.',
          evidence: [
            { metric_name: 'regime_label', value: 1, threshold: null, comparison: null, unit: null },
          ],
        },
        {
          evaluator: 'risk_positioning',
          code: 'RISK_OK',
          severity: 'info',
          title: 'Risk sizing acceptable',
          message: 'Position risk is within limits.',
          evidence: [
            { metric_name: 'position_risk_pct', value: 1.5, threshold: 2.0, comparison: '<', unit: '%' },
          ],
        },
        {
          evaluator: 'exit_logic',
          code: 'EXIT_OK',
          severity: 'info',
          title: 'Exit logic defined',
          message: `R:R of ${rr.toFixed(2)} meets minimum.`,
          evidence: [
            { metric_name: 'risk_reward_ratio', value: rr, threshold: 1.5, comparison: '>=', unit: null },
          ],
        },
      ],
      counts: { info: 3, warning: 0, critical: 0, blocker: 0 },
      evaluators_run: ['regime_fit', 'entry_timing', 'exit_logic', 'risk_positioning', 'behavioral', 'strategy_consistency'],
      evaluated_at: new Date().toISOString(),
    },
    context_summary: null,
  };
}

export async function fetchEvaluators(): Promise<string[]> {
  await delay();
  return ['regime_fit', 'entry_timing', 'exit_logic', 'risk_positioning', 'behavioral', 'strategy_consistency'];
}

// --- Insights ---

export async function fetchInsightsSummary(): Promise<InsightsSummary> {
  await delay();
  return { ...MOCK_INSIGHTS_SUMMARY };
}

export async function fetchRegimeInsights(): Promise<RegimeInsight[]> {
  await delay();
  return [...MOCK_REGIME_INSIGHTS];
}

export async function fetchTimingInsights(): Promise<TimingInsight[]> {
  await delay();
  return [...MOCK_TIMING_INSIGHTS];
}

export async function fetchBehavioralInsights(): Promise<BehavioralInsight[]> {
  await delay();
  return [...MOCK_BEHAVIORAL_INSIGHTS];
}

export async function fetchRiskInsights(): Promise<RiskInsight[]> {
  await delay();
  return [...MOCK_RISK_INSIGHTS];
}

export async function fetchStrategyDriftInsights(): Promise<StrategyDriftInsight[]> {
  await delay();
  return [...MOCK_STRATEGY_DRIFT_INSIGHTS];
}

// --- Journal ---

let journalEntries = [...MOCK_JOURNAL_ENTRIES];

export async function fetchJournalEntries(): Promise<JournalEntry[]> {
  await delay();
  return [...journalEntries];
}

export async function createJournalEntry(entry: JournalEntryCreate): Promise<JournalEntry> {
  await delay();
  const newEntry: JournalEntry = {
    id: `journal-${Date.now()}`,
    date: entry.date,
    type: entry.type,
    content: entry.content,
    trade_id: entry.trade_id ?? null,
    tags: entry.tags ?? [],
    mood: entry.mood ?? null,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };
  journalEntries = [newEntry, ...journalEntries];
  return newEntry;
}

export async function updateJournalEntry(entryId: string, updates: Partial<JournalEntryCreate>): Promise<JournalEntry> {
  await delay();
  const idx = journalEntries.findIndex(e => e.id === entryId);
  if (idx === -1) throw new Error(`Journal entry ${entryId} not found`);
  journalEntries[idx] = {
    ...journalEntries[idx],
    ...updates,
    updated_at: new Date().toISOString(),
  };
  return { ...journalEntries[idx] };
}

export async function fetchBehavioralTags(): Promise<BehavioralTag[]> {
  await delay();
  return [...MOCK_BEHAVIORAL_TAGS];
}

// --- Strategies / Settings ---

export async function fetchStrategies(): Promise<StrategyDefinition[]> {
  await delay();
  return [...MOCK_STRATEGIES];
}

export async function createStrategy(strategy: Omit<StrategyDefinition, 'id'>): Promise<StrategyDefinition> {
  await delay();
  return { ...strategy, id: `strategy-${Date.now()}` };
}

export async function updateStrategy(id: string, updates: Partial<StrategyDefinition>): Promise<StrategyDefinition> {
  await delay();
  const existing = MOCK_STRATEGIES.find(s => s.id === id);
  if (!existing) throw new Error(`Strategy ${id} not found`);
  return { ...existing, ...updates };
}

export async function fetchEvaluationControls(): Promise<EvaluationControls> {
  await delay();
  return { ...MOCK_EVALUATION_CONTROLS };
}

export async function updateEvaluationControls(controls: EvaluationControls): Promise<EvaluationControls> {
  await delay();
  return { ...controls };
}

// --- Onboarding ---

export async function fetchOnboardingStatus(): Promise<OnboardingStatus> {
  await delay();
  return { ...MOCK_ONBOARDING_STATUS };
}

// --- Broker (delegates to mock) ---

export async function fetchBrokerStatus(): Promise<BrokerStatus> {
  await delay();
  return { connected: true, brokerages: ['Robinhood'] };
}
