import type {
  InsightsSummary,
  RegimeInsight,
  TimingInsight,
  BehavioralInsight,
  RiskInsight,
  StrategyDriftInsight,
} from '../../types';

export const MOCK_INSIGHTS_SUMMARY: InsightsSummary = {
  total_trades: 12,
  total_evaluated: 10,
  flagged_count: 5,
  blocker_count: 3,
  avg_score: 62,
  avg_risk_reward: 2.18,
  win_rate: 0.5,
  most_common_flag: 'rushed_entry',
  period: { start: '2025-01-14', end: '2025-01-22' },
};

export const MOCK_REGIME_INSIGHTS: RegimeInsight[] = [
  { regime_label: 'up_trending', trade_count: 4, avg_score: 78, flagged_pct: 10, avg_pnl_pct: 1.55 },
  { regime_label: 'neutral_consolidation', trade_count: 3, avg_score: 65, flagged_pct: 33, avg_pnl_pct: 0.3 },
  { regime_label: 'down_volatile', trade_count: 3, avg_score: 38, flagged_pct: 67, avg_pnl_pct: -1.8 },
  { regime_label: 'high_volatility', trade_count: 2, avg_score: 30, flagged_pct: 100, avg_pnl_pct: null },
];

export const MOCK_TIMING_INSIGHTS: TimingInsight[] = [
  { hour_of_day: 9, trade_count: 4, avg_score: 45, flagged_pct: 50 },
  { hour_of_day: 10, trade_count: 3, avg_score: 68, flagged_pct: 33 },
  { hour_of_day: 11, trade_count: 2, avg_score: 55, flagged_pct: 50 },
  { hour_of_day: 13, trade_count: 2, avg_score: 72, flagged_pct: 0 },
  { hour_of_day: 14, trade_count: 1, avg_score: 80, flagged_pct: 0 },
];

export const MOCK_BEHAVIORAL_INSIGHTS: BehavioralInsight[] = [
  { signal: 'rushed_entry', occurrence_count: 3, pct_of_trades: 25, avg_outcome_pct: -1.5 },
  { signal: 'revenge_trade', occurrence_count: 1, pct_of_trades: 8, avg_outcome_pct: null },
  { signal: 'no_stop_loss', occurrence_count: 1, pct_of_trades: 8, avg_outcome_pct: -2.86 },
  { signal: 'oversized_position', occurrence_count: 2, pct_of_trades: 17, avg_outcome_pct: -2.2 },
];

export const MOCK_RISK_INSIGHTS: RiskInsight[] = [
  { date: '2025-01-14', avg_risk_reward: 2.0, trades_without_stop: 0, max_position_pct: 1.5 },
  { date: '2025-01-15', avg_risk_reward: 2.5, trades_without_stop: 0, max_position_pct: 1.3 },
  { date: '2025-01-16', avg_risk_reward: 2.0, trades_without_stop: 0, max_position_pct: 1.8 },
  { date: '2025-01-17', avg_risk_reward: 2.33, trades_without_stop: 0, max_position_pct: 1.2 },
  { date: '2025-01-18', avg_risk_reward: 3.0, trades_without_stop: 0, max_position_pct: 1.0 },
  { date: '2025-01-19', avg_risk_reward: 0, trades_without_stop: 1, max_position_pct: 4.2 },
  { date: '2025-01-20', avg_risk_reward: 2.33, trades_without_stop: 0, max_position_pct: 1.2 },
  { date: '2025-01-21', avg_risk_reward: 2.67, trades_without_stop: 0, max_position_pct: 0.9 },
  { date: '2025-01-22', avg_risk_reward: 1.85, trades_without_stop: 0, max_position_pct: 2.5 },
];

export const MOCK_STRATEGY_DRIFT_INSIGHTS: StrategyDriftInsight[] = [
  { date: '2025-01-14', consistency_score: 95, deviations: [] },
  { date: '2025-01-15', consistency_score: 90, deviations: [] },
  { date: '2025-01-16', consistency_score: 85, deviations: ['poor_timing'] },
  { date: '2025-01-17', consistency_score: 95, deviations: [] },
  { date: '2025-01-18', consistency_score: 60, deviations: ['direction_mismatch'] },
  { date: '2025-01-19', consistency_score: 40, deviations: ['no_stop_loss', 'oversized_position', 'strategy_mismatch'] },
  { date: '2025-01-20', consistency_score: 50, deviations: ['rushed_entry'] },
  { date: '2025-01-21', consistency_score: 95, deviations: [] },
  { date: '2025-01-22', consistency_score: 55, deviations: ['revenge_trade'] },
];
