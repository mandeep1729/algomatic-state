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

// Helper: compute EMA for a given period
function ema(values: number[], period: number): number[] {
  const result: number[] = [];
  const k = 2 / (period + 1);
  for (let i = 0; i < values.length; i++) {
    if (i === 0) { result.push(values[0]); continue; }
    result.push(+(values[i] * k + result[i - 1] * (1 - k)).toFixed(2));
  }
  return result;
}

// Helper: rolling std dev
function rollingStd(values: number[], period: number): number[] {
  const result: number[] = [];
  for (let i = 0; i < values.length; i++) {
    if (i < period - 1) { result.push(NaN); continue; }
    let sum = 0, sumSq = 0;
    for (let j = i - period + 1; j <= i; j++) { sum += values[j]; sumSq += values[j] ** 2; }
    const mean = sum / period;
    result.push(+Math.sqrt(Math.max(0, sumSq / period - mean ** 2)).toFixed(6));
  }
  return result;
}

// Helper: rolling mean
function rollingMean(values: number[], period: number): number[] {
  const result: number[] = [];
  for (let i = 0; i < values.length; i++) {
    if (i < period - 1) { result.push(NaN); continue; }
    let sum = 0;
    for (let j = i - period + 1; j <= i; j++) sum += values[j];
    result.push(+(sum / period).toFixed(4));
  }
  return result;
}

// Helper: log return over n bars
function logReturn(close: number[], n: number): number[] {
  const result: number[] = [];
  for (let i = 0; i < close.length; i++) {
    if (i < n) { result.push(NaN); continue; }
    result.push(+(Math.log(close[i] / close[i - n])).toFixed(6));
  }
  return result;
}

// Helper: rolling max/min
function rollingMax(values: number[], period: number): number[] {
  const result: number[] = [];
  for (let i = 0; i < values.length; i++) {
    if (i < period - 1) { result.push(NaN); continue; }
    let mx = -Infinity;
    for (let j = i - period + 1; j <= i; j++) mx = Math.max(mx, values[j]);
    result.push(mx);
  }
  return result;
}

function rollingMin(values: number[], period: number): number[] {
  const result: number[] = [];
  for (let i = 0; i < values.length; i++) {
    if (i < period - 1) { result.push(NaN); continue; }
    let mn = Infinity;
    for (let j = i - period + 1; j <= i; j++) mn = Math.min(mn, values[j]);
    result.push(mn);
  }
  return result;
}

function generateMockFeatures(ohlcv: MockOHLCVData): MockFeatureData {
  const { close, open, high, low, volume } = ohlcv;
  const n = close.length;

  const features: Record<string, number[]> = {};

  // --- Returns ---
  features.r1 = logReturn(close, 1);
  features.r5 = logReturn(close, 5);
  features.r15 = logReturn(close, 15);
  features.r60 = logReturn(close, 60);
  // Cumulative return 60
  const cumret: number[] = [];
  for (let i = 0; i < n; i++) {
    if (i < 60) { cumret.push(NaN); continue; }
    let s = 0; for (let j = i - 59; j <= i; j++) s += features.r1[j] ?? 0;
    cumret.push(+s.toFixed(6));
  }
  features.cumret_60 = cumret;

  const ema12 = ema(close, 12);
  const ema48 = ema(close, 48);
  features.ema_diff = close.map((c, i) => +((ema12[i] - ema48[i]) / c).toFixed(6));
  // slope_60 (simplified: linear regression slope using first/last)
  features.slope_60 = close.map((_, i) => {
    if (i < 59) return NaN;
    return +((close[i] - close[i - 59]) / 60).toFixed(4);
  });
  const rv60 = rollingStd(features.r1, 60);
  features.trend_strength = features.slope_60.map((s, i) => {
    if (isNaN(s) || isNaN(rv60[i]) || rv60[i] === 0) return NaN;
    return +(Math.abs(s) / rv60[i]).toFixed(4);
  });

  // --- Volatility ---
  features.rv_15 = rollingStd(features.r1, 15);
  features.rv_60 = rv60;
  features.range_1 = close.map((c, i) => +((high[i] - low[i]) / c).toFixed(6));
  features.atr_60 = rollingMean(features.range_1.map((_, i) => high[i] - low[i]), 60);

  const rangesMean60 = rollingMean(features.range_1, 60);
  const rangesStd60 = rollingStd(features.range_1, 60);
  features.range_z_60 = features.range_1.map((r, i) => {
    if (isNaN(rangesMean60[i]) || isNaN(rangesStd60[i]) || rangesStd60[i] === 0) return NaN;
    return +((r - rangesMean60[i]) / rangesStd60[i]).toFixed(4);
  });
  features.vol_of_vol = rollingStd(features.rv_15, 60);

  // ATR-14
  const trueRange = close.map((_, i) => {
    if (i === 0) return high[0] - low[0];
    return Math.max(high[i] - low[i], Math.abs(high[i] - close[i - 1]), Math.abs(low[i] - close[i - 1]));
  });
  const atr14: number[] = [];
  for (let i = 0; i < n; i++) {
    if (i < 13) { atr14.push(NaN); continue; }
    if (i === 13) {
      let s = 0; for (let j = 0; j <= 13; j++) s += trueRange[j];
      atr14.push(+(s / 14).toFixed(4)); continue;
    }
    atr14.push(+((atr14[i - 1] * 13 + trueRange[i]) / 14).toFixed(4));
  }
  features.atr_14 = atr14;

  // Bollinger Bands
  const sma20 = sma(close, 20);
  const bbStd = rollingStd(close, 20);
  features.bb_upper = sma20.map((m, i) => isNaN(m) ? NaN : +(m + 2 * bbStd[i]).toFixed(2));
  features.bb_middle = sma20;
  features.bb_lower = sma20.map((m, i) => isNaN(m) ? NaN : +(m - 2 * bbStd[i]).toFixed(2));
  features.bb_width = features.bb_upper.map((u, i) => {
    if (isNaN(u) || isNaN(features.bb_lower[i]) || sma20[i] === 0) return NaN;
    return +((u - features.bb_lower[i]) / sma20[i]).toFixed(6);
  });
  features.bb_pct = close.map((c, i) => {
    if (isNaN(features.bb_upper[i])) return NaN;
    const range = features.bb_upper[i] - features.bb_lower[i];
    return range === 0 ? NaN : +((c - features.bb_lower[i]) / range).toFixed(4);
  });

  // --- Volume ---
  features.vol1 = volume.map(v => v);
  features.dvol1 = close.map((c, i) => +(c * volume[i]).toFixed(0));
  const volMean60 = rollingMean(volume.map(v => v), 60);
  features.relvol_60 = volume.map((v, i) => isNaN(volMean60[i]) || volMean60[i] === 0 ? NaN : +(v / volMean60[i]).toFixed(4));
  const volStd60 = rollingStd(volume.map(v => v), 60);
  features.vol_z_60 = volume.map((v, i) => isNaN(volMean60[i]) || volStd60[i] === 0 ? NaN : +((v - volMean60[i]) / volStd60[i]).toFixed(4));
  const dvolArr = features.dvol1;
  const dvolMean60 = rollingMean(dvolArr, 60);
  const dvolStd60 = rollingStd(dvolArr, 60);
  features.dvol_z_60 = dvolArr.map((d, i) => isNaN(dvolMean60[i]) || dvolStd60[i] === 0 ? NaN : +((d - dvolMean60[i]) / dvolStd60[i]).toFixed(4));

  // OBV
  const obv: number[] = [0];
  for (let i = 1; i < n; i++) {
    if (close[i] > close[i - 1]) obv.push(obv[i - 1] + volume[i]);
    else if (close[i] < close[i - 1]) obv.push(obv[i - 1] - volume[i]);
    else obv.push(obv[i - 1]);
  }
  features.obv = obv;

  // VWAP (rolling 60)
  const cumPV: number[] = []; const cumV: number[] = [];
  for (let i = 0; i < n; i++) {
    const tp = (high[i] + low[i] + close[i]) / 3;
    cumPV.push((cumPV[i - 1] ?? 0) + tp * volume[i]);
    cumV.push((cumV[i - 1] ?? 0) + volume[i]);
  }
  features.vwap = cumPV.map((pv, i) => cumV[i] === 0 ? NaN : +(pv / cumV[i]).toFixed(2));
  // vwap_60 (rolling window)
  features.vwap_60 = close.map((_, i) => {
    if (i < 59) return NaN;
    let pv = 0, v = 0;
    for (let j = i - 59; j <= i; j++) { const tp = (high[j] + low[j] + close[j]) / 3; pv += tp * volume[j]; v += volume[j]; }
    return v === 0 ? NaN : +(pv / v).toFixed(2);
  });

  // --- Intrabar ---
  features.clv = close.map((c, i) => {
    const hl = high[i] - low[i];
    return hl === 0 ? 0 : +(((c - low[i]) - (high[i] - c)) / hl).toFixed(4);
  });
  features.body_ratio = close.map((c, i) => {
    const hl = high[i] - low[i];
    return hl === 0 ? 0 : +(Math.abs(c - open[i]) / hl).toFixed(4);
  });
  features.upper_wick = close.map((c, i) => {
    const hl = high[i] - low[i];
    return hl === 0 ? 0 : +((high[i] - Math.max(c, open[i])) / hl).toFixed(4);
  });
  features.lower_wick = close.map((c, i) => {
    const hl = high[i] - low[i];
    return hl === 0 ? 0 : +((Math.min(c, open[i]) - low[i]) / hl).toFixed(4);
  });

  // --- Anchor ---
  features.dist_vwap_60 = close.map((c, i) => isNaN(features.vwap_60[i]) ? NaN : +((c - features.vwap_60[i]) / c).toFixed(6));
  features.dist_ema_48 = close.map((c, i) => +((c - ema48[i]) / c).toFixed(6));
  const high20 = rollingMax(high, 20);
  features.breakout_20 = close.map((c, i) => isNaN(high20[i]) ? NaN : c >= high20[i] ? 1 : 0);
  features.pullback_depth = close.map((c, i) => isNaN(high20[i]) ? NaN : +((high20[i] - c) / high20[i]).toFixed(6));

  // --- Time ---
  features.tod_sin = ohlcv.timestamps.map(ts => {
    const d = new Date(ts); const mins = d.getHours() * 60 + d.getMinutes();
    return +(Math.sin(2 * Math.PI * mins / 1440)).toFixed(4);
  });
  features.tod_cos = ohlcv.timestamps.map(ts => {
    const d = new Date(ts); const mins = d.getHours() * 60 + d.getMinutes();
    return +(Math.cos(2 * Math.PI * mins / 1440)).toFixed(4);
  });
  features.is_open_window = ohlcv.timestamps.map(ts => {
    const d = new Date(ts); const mins = d.getHours() * 60 + d.getMinutes();
    return (mins >= 570 && mins < 600) ? 1 : 0; // 9:30-10:00
  });
  features.is_close_window = ohlcv.timestamps.map(ts => {
    const d = new Date(ts); const mins = d.getHours() * 60 + d.getMinutes();
    return (mins >= 900 && mins < 960) ? 1 : 0; // 15:00-16:00
  });
  features.is_midday = ohlcv.timestamps.map(ts => {
    const d = new Date(ts); const mins = d.getHours() * 60 + d.getMinutes();
    return (mins >= 720 && mins < 810) ? 1 : 0; // 12:00-13:30
  });

  // --- Market Context (synthetic — use close as proxy) ---
  features.mkt_r5 = logReturn(close, 5);
  features.mkt_r15 = logReturn(close, 15);
  features.mkt_rv_60 = rv60;
  features.beta_60 = close.map(() => +(0.8 + Math.random() * 0.4).toFixed(4));
  features.resid_rv_60 = rv60.map(v => isNaN(v) ? NaN : +(v * (0.3 + Math.random() * 0.3)).toFixed(6));

  // --- Momentum ---
  // RSI-14
  const rsi: number[] = [NaN];
  let avgGain = 0, avgLoss = 0;
  for (let i = 1; i < n; i++) {
    const diff = close[i] - close[i - 1];
    if (i <= 14) {
      avgGain += Math.max(diff, 0); avgLoss += Math.max(-diff, 0);
      if (i < 14) { rsi.push(NaN); continue; }
      avgGain /= 14; avgLoss /= 14;
    } else {
      avgGain = (avgGain * 13 + Math.max(diff, 0)) / 14;
      avgLoss = (avgLoss * 13 + Math.max(-diff, 0)) / 14;
    }
    const rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
    rsi.push(+(100 - 100 / (1 + rs)).toFixed(2));
  }
  features.rsi_14 = rsi;

  // MACD
  const ema26 = ema(close, 26);
  const macdLine = ema12.map((e, i) => +(e - ema26[i]).toFixed(4));
  const macdSignal = ema(macdLine, 9);
  features.macd = macdLine;
  features.macd_signal = macdSignal;
  features.macd_hist = macdLine.map((m, i) => +(m - macdSignal[i]).toFixed(4));

  // Stochastic
  const low14 = rollingMin(low, 14);
  const high14 = rollingMax(high, 14);
  const stochK = close.map((c, i) => {
    if (isNaN(low14[i]) || isNaN(high14[i])) return NaN;
    const range = high14[i] - low14[i];
    return range === 0 ? 50 : +((c - low14[i]) / range * 100).toFixed(2);
  });
  features.stoch_k = stochK;
  features.stoch_d = sma(stochK.map(v => isNaN(v) ? 0 : v), 3);

  // ADX-14
  const dx: number[] = [];
  let pdiSmooth = 0, ndiSmooth = 0, trSmooth = 0;
  for (let i = 0; i < n; i++) {
    if (i === 0) { dx.push(NaN); continue; }
    const upMove = high[i] - high[i - 1];
    const downMove = low[i - 1] - low[i];
    const pDM = upMove > downMove && upMove > 0 ? upMove : 0;
    const nDM = downMove > upMove && downMove > 0 ? downMove : 0;
    if (i <= 14) {
      pdiSmooth += pDM; ndiSmooth += nDM; trSmooth += trueRange[i];
      if (i < 14) { dx.push(NaN); continue; }
    } else {
      pdiSmooth = pdiSmooth - pdiSmooth / 14 + pDM;
      ndiSmooth = ndiSmooth - ndiSmooth / 14 + nDM;
      trSmooth = trSmooth - trSmooth / 14 + trueRange[i];
    }
    const pdi = trSmooth === 0 ? 0 : pdiSmooth / trSmooth * 100;
    const ndi = trSmooth === 0 ? 0 : ndiSmooth / trSmooth * 100;
    const diSum = pdi + ndi;
    dx.push(diSum === 0 ? 0 : +((Math.abs(pdi - ndi) / diSum) * 100).toFixed(2));
  }
  features.adx_14 = sma(dx.map(v => isNaN(v) ? 0 : v), 14);

  // CCI-20
  const tp = close.map((c, i) => (high[i] + low[i] + c) / 3);
  const tpMean20 = rollingMean(tp, 20);
  features.cci_20 = tp.map((t, i) => {
    if (isNaN(tpMean20[i])) return NaN;
    let mad = 0;
    for (let j = i - 19; j <= i; j++) mad += Math.abs(tp[j] - tpMean20[i]);
    mad /= 20;
    return mad === 0 ? 0 : +((t - tpMean20[i]) / (0.015 * mad)).toFixed(2);
  });

  // Williams %R
  features.willr_14 = close.map((c, i) => {
    if (isNaN(high14[i])) return NaN;
    const range = high14[i] - low14[i];
    return range === 0 ? -50 : +(((high14[i] - c) / range) * -100).toFixed(2);
  });

  // MFI-14
  const typicalPrice = tp;
  const rawMF = typicalPrice.map((t, i) => t * volume[i]);
  const mfi: number[] = [];
  for (let i = 0; i < n; i++) {
    if (i < 14) { mfi.push(NaN); continue; }
    let posMF = 0, negMF = 0;
    for (let j = i - 13; j <= i; j++) {
      if (j > 0 && typicalPrice[j] > typicalPrice[j - 1]) posMF += rawMF[j];
      else if (j > 0) negMF += rawMF[j];
    }
    const ratio = negMF === 0 ? 100 : posMF / negMF;
    mfi.push(+(100 - 100 / (1 + ratio)).toFixed(2));
  }
  features.mfi_14 = mfi;

  // --- Trend ---
  features.sma_20 = sma20;
  features.sma_50 = sma(close, 50);
  features.sma_200 = sma(close, 200);
  features.ema_20 = ema(close, 20);
  features.ema_50 = ema(close, 50);
  features.ema_200 = ema(close, 200);

  // PSAR (simplified)
  const psar: number[] = [];
  let isUptrend = true;
  let psarVal = low[0];
  let ep = high[0];
  let af = 0.02;
  for (let i = 0; i < n; i++) {
    if (i === 0) { psar.push(psarVal); continue; }
    psarVal = psarVal + af * (ep - psarVal);
    if (isUptrend) {
      if (low[i] < psarVal) {
        isUptrend = false; psarVal = ep; ep = low[i]; af = 0.02;
      } else {
        if (high[i] > ep) { ep = high[i]; af = Math.min(af + 0.02, 0.2); }
      }
    } else {
      if (high[i] > psarVal) {
        isUptrend = true; psarVal = ep; ep = high[i]; af = 0.02;
      } else {
        if (low[i] < ep) { ep = low[i]; af = Math.min(af + 0.02, 0.2); }
      }
    }
    psar.push(+psarVal.toFixed(2));
  }
  features.psar = psar;

  // Ichimoku
  const ichi9h = rollingMax(high, 9);
  const ichi9l = rollingMin(low, 9);
  const ichi26h = rollingMax(high, 26);
  const ichi26l = rollingMin(low, 26);
  const ichi52h = rollingMax(high, 52);
  const ichi52l = rollingMin(low, 52);
  features.ichi_tenkan = ichi9h.map((h, i) => isNaN(h) || isNaN(ichi9l[i]) ? NaN : +((h + ichi9l[i]) / 2).toFixed(2));
  features.ichi_kijun = ichi26h.map((h, i) => isNaN(h) || isNaN(ichi26l[i]) ? NaN : +((h + ichi26l[i]) / 2).toFixed(2));
  features.ichi_senkou_a = features.ichi_tenkan.map((t, i) => isNaN(t) || isNaN(features.ichi_kijun[i]) ? NaN : +((t + features.ichi_kijun[i]) / 2).toFixed(2));
  features.ichi_senkou_b = ichi52h.map((h, i) => isNaN(h) || isNaN(ichi52l[i]) ? NaN : +((h + ichi52l[i]) / 2).toFixed(2));
  features.ichi_chikou = close.map((_, i) => i >= 26 ? close[i - 26] : NaN);

  // --- Support/Resistance (pivot points from prev bar) ---
  features.pivot_pp = close.map((_, i) => i === 0 ? NaN : +((high[i - 1] + low[i - 1] + close[i - 1]) / 3).toFixed(2));
  features.pivot_r1 = features.pivot_pp.map((pp, i) => isNaN(pp) ? NaN : +(2 * pp - low[i - 1]).toFixed(2));
  features.pivot_r2 = features.pivot_pp.map((pp, i) => isNaN(pp) ? NaN : +(pp + (high[i - 1] - low[i - 1])).toFixed(2));
  features.pivot_s1 = features.pivot_pp.map((pp, i) => isNaN(pp) ? NaN : +(2 * pp - high[i - 1]).toFixed(2));
  features.pivot_s2 = features.pivot_pp.map((pp, i) => isNaN(pp) ? NaN : +(pp - (high[i - 1] - low[i - 1])).toFixed(2));

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
