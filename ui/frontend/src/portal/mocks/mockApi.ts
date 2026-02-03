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

// --- OHLCV & Features (mock chart data) ---

interface MockOHLCVData {
  timestamps: string[];
  open: number[];
  high: number[];
  low: number[];
  close: number[];
  volume: number[];
}

interface MockFeatureData {
  timestamps: string[];
  features: Record<string, number[]>;
  feature_names: string[];
}

// Seed prices for known symbols, fallback for unknowns
const SEED_PRICES: Record<string, number> = {
  AAPL: 185, TSLA: 245, NVDA: 480, MSFT: 410, SPY: 520, AMZN: 180, META: 490, GOOG: 155,
};

function generateMockOHLCV(symbol: string, bars = 200): MockOHLCVData {
  const basePrice = SEED_PRICES[symbol] ?? 100;
  const timestamps: string[] = [];
  const open: number[] = [];
  const high: number[] = [];
  const low: number[] = [];
  const close: number[] = [];
  const volume: number[] = [];

  let price = basePrice;
  // Start 200 bars ago in 5-min increments
  const startMs = Date.now() - bars * 5 * 60 * 1000;

  for (let i = 0; i < bars; i++) {
    const ts = new Date(startMs + i * 5 * 60 * 1000).toISOString();
    timestamps.push(ts);

    const change = (Math.random() - 0.48) * basePrice * 0.005;
    const o = price;
    const c = +(price + change).toFixed(2);
    const h = +Math.max(o, c, o + Math.random() * basePrice * 0.003).toFixed(2);
    const l = +Math.min(o, c, o - Math.random() * basePrice * 0.003).toFixed(2);
    const v = Math.floor(50000 + Math.random() * 200000);

    open.push(o);
    high.push(h);
    low.push(l);
    close.push(c);
    volume.push(v);
    price = c;
  }

  return { timestamps, open, high, low, close, volume };
}

function sma(values: number[], period: number): number[] {
  const result: number[] = [];
  for (let i = 0; i < values.length; i++) {
    if (i < period - 1) { result.push(NaN); continue; }
    let sum = 0;
    for (let j = i - period + 1; j <= i; j++) sum += values[j];
    result.push(+(sum / period).toFixed(2));
  }
  return result;
}

function generateMockFeatures(ohlcv: MockOHLCVData): MockFeatureData {
  const { close, high, low, volume } = ohlcv;
  const n = close.length;

  // SMA overlays
  const sma20 = sma(close, 20);
  const sma50 = sma(close, 50);

  // EMA-20
  const ema20: number[] = [];
  const k = 2 / 21;
  for (let i = 0; i < n; i++) {
    if (i === 0) { ema20.push(close[0]); continue; }
    ema20.push(+(close[i] * k + ema20[i - 1] * (1 - k)).toFixed(2));
  }

  // Bollinger Bands
  const bbUpper: number[] = [];
  const bbLower: number[] = [];
  for (let i = 0; i < n; i++) {
    if (isNaN(sma20[i])) { bbUpper.push(NaN); bbLower.push(NaN); continue; }
    let sumSq = 0;
    for (let j = i - 19; j <= i; j++) sumSq += (close[j] - sma20[i]) ** 2;
    const std = Math.sqrt(sumSq / 20);
    bbUpper.push(+(sma20[i] + 2 * std).toFixed(2));
    bbLower.push(+(sma20[i] - 2 * std).toFixed(2));
  }

  // RSI-14
  const rsi: number[] = [NaN];
  let avgGain = 0, avgLoss = 0;
  for (let i = 1; i < n; i++) {
    const diff = close[i] - close[i - 1];
    if (i <= 14) {
      avgGain += Math.max(diff, 0);
      avgLoss += Math.max(-diff, 0);
      if (i < 14) { rsi.push(NaN); continue; }
      avgGain /= 14; avgLoss /= 14;
    } else {
      avgGain = (avgGain * 13 + Math.max(diff, 0)) / 14;
      avgLoss = (avgLoss * 13 + Math.max(-diff, 0)) / 14;
    }
    const rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
    rsi.push(+(100 - 100 / (1 + rs)).toFixed(2));
  }

  // ATR-14
  const atr: number[] = [NaN];
  for (let i = 1; i < n; i++) {
    const tr = Math.max(high[i] - low[i], Math.abs(high[i] - close[i - 1]), Math.abs(low[i] - close[i - 1]));
    if (i < 14) { atr.push(NaN); continue; }
    if (i === 14) {
      let sum = 0;
      for (let j = 1; j <= 14; j++) sum += Math.max(high[j] - low[j], Math.abs(high[j] - close[j - 1]), Math.abs(low[j] - close[j - 1]));
      atr.push(+(sum / 14).toFixed(4));
    } else {
      atr.push(+((atr[i - 1] * 13 + tr) / 14).toFixed(4));
    }
  }

  // OBV
  const obv: number[] = [0];
  for (let i = 1; i < n; i++) {
    if (close[i] > close[i - 1]) obv.push(obv[i - 1] + volume[i]);
    else if (close[i] < close[i - 1]) obv.push(obv[i - 1] - volume[i]);
    else obv.push(obv[i - 1]);
  }

  const features: Record<string, number[]> = {
    sma_20: sma20,
    sma_50: sma50,
    ema_20: ema20,
    bb_upper: bbUpper,
    bb_middle: sma20,
    bb_lower: bbLower,
    rsi_14: rsi,
    atr_14: atr,
    obv: obv,
  };

  return {
    timestamps: ohlcv.timestamps,
    features,
    feature_names: Object.keys(features),
  };
}

// Cache so re-clicking the same symbol returns consistent data
const ohlcvCache = new Map<string, MockOHLCVData>();

export async function fetchMockOHLCVData(symbol: string): Promise<MockOHLCVData> {
  await delay(300);
  if (!ohlcvCache.has(symbol)) {
    ohlcvCache.set(symbol, generateMockOHLCV(symbol));
  }
  return ohlcvCache.get(symbol)!;
}

export async function fetchMockFeatures(symbol: string): Promise<MockFeatureData> {
  await delay(100);
  // Ensure OHLCV exists first
  if (!ohlcvCache.has(symbol)) {
    ohlcvCache.set(symbol, generateMockOHLCV(symbol));
  }
  return generateMockFeatures(ohlcvCache.get(symbol)!);
}
