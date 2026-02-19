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
  favorite_tickers?: string[];
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

/** Summary of decision context for a trade fill */
export interface ContextSummary {
  strategy: string | null;
  emotions: string | null;
  hypothesis_snippet: string | null;
}

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
  context_summary: ContextSummary | null;
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
  legQuantities: number[];
  overallLabel: OverallLabel;
  keyFlags: string[];
  /** Unique strategy tags used across all legs of this campaign */
  strategies: string[];
  /** Broker order IDs from trade fills */
  orderIds?: string[];
  /** Realized PnL for closed campaigns */
  pnlRealized?: number;
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
  campaignId: string | null;
  legType: LegType;
  side: 'buy' | 'sell';
  quantity: number;
  avgPrice: number;
  startedAt: string;
  endedAt: string;
  symbol?: string;
  direction?: string;
  orderIds?: string[];
  strategyName?: string;
}

export interface OrphanedLegGroup {
  symbol: string;
  legs: OrphanedLeg[];
}

export interface OrphanedLeg {
  legId: string;
  legType: LegType;
  side: 'buy' | 'sell';
  quantity: number;
  avgPrice: number;
  startedAt: string;
  endedAt?: string;
  symbol: string;
  direction: string;
  strategyName?: string;
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

// --- Campaign Checks (behavioral nudges) ---

export type CheckSeverity = 'info' | 'warn' | 'critical';

export interface CampaignCheck {
  checkId: string;
  legId: string;
  checkType: string;
  code: string;
  severity: CheckSeverity;
  passed: boolean;
  nudgeText: string | null;
  details: Record<string, unknown> | null;
  checkPhase: string;
  checkedAt: string;
  acknowledged: boolean | null;
  traderAction: string | null;
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
  checksByLeg: Record<string, CampaignCheck[]>;
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

// --- Site Preferences (table column visibility, etc.) ---

export interface SitePrefs {
  table_columns: Record<string, string[]>;
}

// --- Fill Context (for editing context from Transactions view) ---

export interface FillContextDetail {
  fill_id: number;
  context_id: number | null;
  context_type: string | null;
  strategy_id: number | null;
  strategy_name: string | null;
  hypothesis: string | null;
  exit_intent: string | null;
  feelings_then: { chips: string[]; intensity?: number; note?: string } | null;
  feelings_now: { chips: string[]; intensity?: number; note?: string } | null;
  notes: string | null;
  updated_at: string | null;
}

export interface SaveFillContextRequest {
  strategy_id?: number | null;
  hypothesis?: string | null;
  exit_intent?: string | null;
  feelings_then?: { chips: string[]; intensity?: number; note?: string } | null;
  feelings_now?: { chips: string[]; intensity?: number; note?: string } | null;
  notes?: string | null;
}

// --- Trading Agents ---

export type AgentStatus = 'created' | 'active' | 'paused' | 'stopped' | 'error';
export type AgentTimeframe = '1Min' | '5Min' | '15Min' | '1Hour' | '1Day';
export type StrategyCategory = 'trend' | 'mean_reversion' | 'breakout' | 'volume_flow' | 'pattern' | 'regime' | 'custom';
export type StrategyDirection = 'long_short' | 'long_only' | 'short_only';

export interface AgentStrategy {
  id: number;
  name: string;
  display_name: string;
  description: string | null;
  category: string;
  direction: string;
  atr_stop_mult: number | null;
  atr_target_mult: number | null;
  trailing_atr_mult: number | null;
  time_stop_bars: number | null;
  required_features: string[] | null;
  is_predefined: boolean;
  source_strategy_id: number | null;
  is_active: boolean;
}

export interface AgentSummary {
  id: number;
  name: string;
  symbol: string;
  strategy_id: number;
  strategy_name: string | null;
  status: AgentStatus;
  timeframe: string;
  interval_minutes: number;
  lookback_days: number;
  position_size_dollars: number;
  risk_config: Record<string, unknown> | null;
  exit_config: Record<string, unknown> | null;
  paper: boolean;
  last_run_at: string | null;
  last_signal: string | null;
  error_message: string | null;
  consecutive_errors: number;
  current_position: {
    direction: string;
    quantity: number;
    entry_price: number;
    entry_time: string;
  } | null;
  created_at: string;
  updated_at: string;
}

export interface AgentCreateRequest {
  name: string;
  symbol: string;
  strategy_id: number;
  timeframe?: string;
  interval_minutes?: number;
  lookback_days?: number;
  position_size_dollars: number;
  paper?: boolean;
}

export interface AgentUpdateRequest {
  name?: string;
  symbol?: string;
  strategy_id?: number;
  timeframe?: string;
  interval_minutes?: number;
  lookback_days?: number;
  position_size_dollars?: number;
  paper?: boolean;
}

export interface AgentOrder {
  id: number;
  symbol: string;
  side: string;
  quantity: number;
  order_type: string;
  limit_price: number | null;
  stop_price: number | null;
  client_order_id: string;
  broker_order_id: string | null;
  status: string;
  filled_quantity: number | null;
  filled_avg_price: number | null;
  signal_direction: string | null;
  signal_metadata: Record<string, unknown> | null;
  submitted_at: string | null;
  filled_at: string | null;
  created_at: string;
}

export interface AgentActivity {
  id: number;
  activity_type: string;
  message: string;
  details: Record<string, unknown> | null;
  severity: string;
  created_at: string;
}
