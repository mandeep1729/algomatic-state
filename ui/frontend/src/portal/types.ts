// =============================================================================
// Trading Buddy Portal Types
// =============================================================================

// --- User & Auth ---

export interface User {
  id: number;
  email: string;
  name: string;
  profile_picture_url?: string | null;
  google_id?: string | null;
  auth_provider?: string;
  onboarding_complete: boolean;
  created_at: string;
}

export interface TradingProfile {
  experience_level: 'beginner' | 'intermediate' | 'advanced';
  trading_style: 'day_trading' | 'swing' | 'scalping' | 'position';
  primary_markets: string[];
  typical_timeframes: string[];
  account_size_range: string;
}

export interface RiskPreferences {
  max_loss_per_trade_pct: number;
  max_daily_loss_pct: number;
  max_open_positions: number;
  risk_reward_minimum: number;
  stop_loss_required: boolean;
}

// --- Trades ---

export type TradeSource = 'synced' | 'manual' | 'csv' | 'proposed';
export type TradeStatus = 'open' | 'closed' | 'proposed';
export type TradeDirection = 'long' | 'short';

export interface TradeSummary {
  id: string;
  symbol: string;
  direction: TradeDirection;
  entry_price: number;
  exit_price: number | null;
  quantity: number;
  entry_time: string;
  exit_time: string | null;
  source: TradeSource;
  brokerage: string | null;
  is_flagged: boolean;
  flag_count: number;
  status: TradeStatus;
  timeframe: string;
}

export interface TradeListResponse {
  trades: TradeSummary[];
  total: number;
  page: number;
  limit: number;
}

export interface TradeDetail extends TradeSummary {
  stop_loss: number | null;
  profit_target: number | null;
  risk_reward_ratio: number | null;
  pnl: number | null;
  pnl_pct: number | null;
  evaluation: EvaluationResponse | null;
  notes: string | null;
  tags: string[];
}

// --- Evaluation ---

export type Severity = 'info' | 'warning' | 'critical' | 'blocker';

export interface EvidenceResponse {
  metric_name: string;
  value: number;
  threshold: number | null;
  comparison: '<' | '<=' | '>' | '>=' | '==' | '!=' | null;
  unit: string | null;
}

export interface EvaluationItemResponse {
  evaluator: string;
  code: string;
  severity: Severity;
  title: string;
  message: string;
  evidence: EvidenceResponse[];
}

export interface EvaluationResponse {
  score: number;
  summary: string;
  has_blockers: boolean;
  top_issues: EvaluationItemResponse[];
  all_items: EvaluationItemResponse[];
  counts: Record<string, number>;
  evaluators_run: string[];
  evaluated_at: string;
}

export interface TradeIntentCreate {
  symbol: string;
  direction: TradeDirection;
  timeframe: string;
  entry_price: number;
  stop_loss: number;
  profit_target: number;
  position_size?: number;
  position_value?: number;
  rationale?: string;
}

export interface TradeIntentResponse {
  intent_id: number | null;
  symbol: string;
  direction: string;
  timeframe: string;
  entry_price: number;
  stop_loss: number;
  profit_target: number;
  position_size: number | null;
  position_value: number | null;
  rationale: string | null;
  status: string;
  risk_reward_ratio: number;
  total_risk: number | null;
  created_at: string;
}

export interface EvaluateRequest {
  intent: TradeIntentCreate;
  evaluators?: string[];
  include_context: boolean;
}

export interface EvaluateResponse {
  intent: TradeIntentResponse;
  evaluation: EvaluationResponse;
  context_summary: Record<string, unknown> | null;
}

// --- Insights ---

export interface InsightsSummary {
  total_trades: number;
  total_evaluated: number;
  flagged_count: number;
  blocker_count: number;
  avg_score: number;
  avg_risk_reward: number;
  win_rate: number | null;
  most_common_flag: string | null;
  period: { start: string; end: string };
}

export interface RegimeInsight {
  regime_label: string;
  trade_count: number;
  avg_score: number;
  flagged_pct: number;
  avg_pnl_pct: number | null;
}

export interface TimingInsight {
  hour_of_day: number;
  trade_count: number;
  avg_score: number;
  flagged_pct: number;
}

export interface BehavioralInsight {
  signal: string;
  occurrence_count: number;
  pct_of_trades: number;
  avg_outcome_pct: number | null;
}

export interface RiskInsight {
  date: string;
  avg_risk_reward: number;
  trades_without_stop: number;
  max_position_pct: number;
}

export interface StrategyDriftInsight {
  date: string;
  consistency_score: number;
  deviations: string[];
}

// --- Journal ---

export type JournalEntryType = 'daily_reflection' | 'trade_note';
export type Mood = 'confident' | 'neutral' | 'anxious' | 'frustrated';

export interface JournalEntry {
  id: string;
  date: string;
  type: JournalEntryType;
  content: string;
  trade_id: string | null;
  tags: string[];
  mood: Mood | null;
  created_at: string;
  updated_at: string;
}

export interface JournalEntryCreate {
  date: string;
  type: JournalEntryType;
  content: string;
  trade_id?: string;
  tags?: string[];
  mood?: Mood;
}

export type TagCategory = 'emotional' | 'process' | 'risk' | 'timing';

export interface BehavioralTag {
  name: string;
  category: TagCategory;
  description: string;
}

// --- Settings / Strategies ---

export interface StrategyDefinition {
  id: string;
  name: string;
  description: string;
  direction: TradeDirection | 'both';
  timeframes: string[];
  entry_criteria: string;
  exit_criteria: string;
  max_risk_pct: number;
  min_risk_reward: number;
  is_active: boolean;
}

export interface EvaluationControls {
  evaluators_enabled: Record<string, boolean>;
  auto_evaluate_synced: boolean;
  notification_on_blocker: boolean;
  severity_threshold: Severity;
}

// --- Onboarding ---

export interface OnboardingStatus {
  profile_complete: boolean;
  risk_complete: boolean;
  strategy_complete: boolean;
  broker_connected: boolean;
  all_complete: boolean;
}

// --- Ticker PnL ---

export interface TickerPnlSummary {
  symbol: string;
  total_pnl: number;
  total_pnl_pct: number;
  trade_count: number;
  closed_count: number;
  first_entry_time: string;
}

/** Cumulative PnL timeseries aligned to OHLCV chart timestamps. */
export interface PnlTimeseries {
  timestamps: string[];
  cumulative_pnl: number[];
}

// --- Position Campaigns ---

export type CampaignStatus = 'open' | 'closed';
export type LegType = 'open' | 'add' | 'reduce' | 'close';
export type EvalScope = 'campaign' | 'leg' | 'idea';
export type OverallLabel = 'aligned' | 'mixed' | 'fragile' | 'deviates';
export type CampaignSeverity = 'info' | 'low' | 'medium' | 'high';
export type DimensionKey =
  | 'regime_fit'
  | 'entry_timing'
  | 'exit_logic'
  | 'risk_structure'
  | 'behavioral'
  | 'strategy_consistency';

export interface CampaignSummary {
  campaignId: string;
  symbol: string;
  direction: TradeDirection;
  status: CampaignStatus;
  openedAt: string;
  closedAt?: string;
  legsCount: number;
  maxQty: number;
  overallLabel: OverallLabel;
  keyFlags: string[];
}

export interface Campaign {
  campaignId: string;
  symbol: string;
  direction: TradeDirection;
  status: CampaignStatus;
  openedAt: string;
  closedAt?: string;
  legsCount: number;
  maxQty: number;
  pnlRealized?: number;
  costBasisMethod: 'average' | 'fifo' | 'lifo';
  source: 'broker_synced' | 'manual' | 'proposed';
}

export interface CampaignLeg {
  legId: string;
  campaignId: string;
  legType: LegType;
  side: 'buy' | 'sell';
  quantity: number;
  avgPrice: number;
  startedAt: string;
  endedAt: string;
}

export interface EvaluationDimension {
  dimensionKey: DimensionKey;
  severity: CampaignSeverity;
  label: string;
  explanation: string;
  evidence?: Record<string, unknown>;
  visuals?: Record<string, unknown>;
}

export interface EvaluationBundle {
  bundleId: string;
  evalScope: EvalScope;
  overallLabel: OverallLabel;
  dimensions: EvaluationDimension[];
}

export interface DecisionContext {
  contextId: string;
  scope: 'campaign' | 'leg' | 'idea';
  campaignId?: string;
  legId?: string;
  ideaId?: string;
  contextType: 'entry' | 'add' | 'reduce' | 'exit' | 'post_trade_reflection';
  strategyTags: string[];
  hypothesis?: string;
  exitIntent?: 'fixed' | 'trail' | 'scale' | 'time' | 'unknown';
  feelingsThen?: { chips: string[]; intensity?: number; note?: string };
  feelingsNow?: { chips: string[]; intensity?: number; note?: string };
  notes?: string;
  updatedAt: string;
}

export interface CampaignDetail {
  campaign: Campaign;
  legs: CampaignLeg[];
  evaluationCampaign: EvaluationBundle;
  evaluationByLeg: Record<string, EvaluationBundle>;
  contextsByLeg: Record<string, DecisionContext | undefined>;
}

// --- Broker (re-export from existing types for convenience) ---

export interface BrokerConnectResponse {
  redirect_url: string;
}

export interface BrokerSyncResponse {
  status: string;
  trades_synced: number;
}

export interface BrokerStatus {
  connected: boolean;
  brokerages: string[];
}
