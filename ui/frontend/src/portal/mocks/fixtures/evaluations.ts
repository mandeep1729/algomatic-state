import type { EvaluationResponse } from '../../types';

// Full evaluation bundles keyed by trade ID
export const MOCK_EVALUATIONS: Record<string, EvaluationResponse> = {
  'trade-001': {
    score: 35,
    summary: 'Trade entered during unfavorable regime with rushed timing. Two blockers identified.',
    has_blockers: true,
    top_issues: [
      {
        evaluator: 'regime_fit',
        code: 'REGIME_UNFAVORABLE',
        severity: 'blocker',
        title: 'Unfavorable market regime',
        message: 'Current regime is high-volatility downtrend. Long entries in this regime have a 72% loss rate historically.',
        evidence: [
          { metric_name: 'regime_label', value: 3, threshold: null, comparison: null, unit: null },
          { metric_name: 'regime_win_rate', value: 0.28, threshold: 0.45, comparison: '<', unit: '%' },
        ],
      },
      {
        evaluator: 'behavioral',
        code: 'RUSHED_ENTRY',
        severity: 'blocker',
        title: 'Rushed entry detected',
        message: 'Trade was placed within 5 minutes of market open with no prior analysis session. This pattern correlates with impulsive decisions.',
        evidence: [
          { metric_name: 'time_since_open', value: 5, threshold: 15, comparison: '<', unit: 'minutes' },
          { metric_name: 'analysis_session_duration', value: 0, threshold: 5, comparison: '<', unit: 'minutes' },
        ],
      },
    ],
    all_items: [
      {
        evaluator: 'regime_fit',
        code: 'REGIME_UNFAVORABLE',
        severity: 'blocker',
        title: 'Unfavorable market regime',
        message: 'Current regime is high-volatility downtrend. Long entries in this regime have a 72% loss rate historically.',
        evidence: [
          { metric_name: 'regime_label', value: 3, threshold: null, comparison: null, unit: null },
          { metric_name: 'regime_win_rate', value: 0.28, threshold: 0.45, comparison: '<', unit: '%' },
        ],
      },
      {
        evaluator: 'behavioral',
        code: 'RUSHED_ENTRY',
        severity: 'blocker',
        title: 'Rushed entry detected',
        message: 'Trade was placed within 5 minutes of market open with no prior analysis session.',
        evidence: [
          { metric_name: 'time_since_open', value: 5, threshold: 15, comparison: '<', unit: 'minutes' },
          { metric_name: 'analysis_session_duration', value: 0, threshold: 5, comparison: '<', unit: 'minutes' },
        ],
      },
      {
        evaluator: 'entry_timing',
        code: 'ENTRY_TIMING_POOR',
        severity: 'warning',
        title: 'Entry timing could be better',
        message: 'Entry was made near intraday resistance. Price was within 0.2% of the 20-bar high.',
        evidence: [
          { metric_name: 'distance_to_resistance', value: 0.2, threshold: 0.5, comparison: '<', unit: '%' },
        ],
      },
      {
        evaluator: 'risk_positioning',
        code: 'RISK_OK',
        severity: 'info',
        title: 'Risk sizing acceptable',
        message: 'Position size is within declared risk limits.',
        evidence: [
          { metric_name: 'position_risk_pct', value: 1.2, threshold: 2.0, comparison: '<', unit: '%' },
        ],
      },
      {
        evaluator: 'exit_logic',
        code: 'EXIT_OK',
        severity: 'info',
        title: 'Exit logic defined',
        message: 'Stop loss and profit target are set with acceptable R:R.',
        evidence: [
          { metric_name: 'risk_reward_ratio', value: 2.33, threshold: 1.5, comparison: '>=', unit: null },
        ],
      },
      {
        evaluator: 'strategy_consistency',
        code: 'STRATEGY_OK',
        severity: 'info',
        title: 'Consistent with declared strategy',
        message: 'Trade matches declared day-trading long strategy on 5Min timeframe.',
        evidence: [],
      },
    ],
    counts: { info: 3, warning: 1, critical: 0, blocker: 2 },
    evaluators_run: ['regime_fit', 'entry_timing', 'exit_logic', 'risk_positioning', 'behavioral', 'strategy_consistency'],
    evaluated_at: '2025-01-20T10:16:00Z',
  },

  'trade-003': {
    score: 42,
    summary: 'Trade has no stop loss and oversized position. Strategy mismatch flagged.',
    has_blockers: false,
    top_issues: [
      {
        evaluator: 'risk_positioning',
        code: 'NO_STOP_LOSS',
        severity: 'critical',
        title: 'No stop loss defined',
        message: 'This trade has no stop loss. Risk preferences require a stop loss on every trade.',
        evidence: [
          { metric_name: 'stop_loss_defined', value: 0, threshold: 1, comparison: '<', unit: 'boolean' },
        ],
      },
      {
        evaluator: 'risk_positioning',
        code: 'OVERSIZED_POSITION',
        severity: 'warning',
        title: 'Position size exceeds guidelines',
        message: 'Position represents 4.2% of account, exceeding the 2% max risk per trade guideline.',
        evidence: [
          { metric_name: 'position_risk_pct', value: 4.2, threshold: 2.0, comparison: '>', unit: '%' },
        ],
      },
      {
        evaluator: 'strategy_consistency',
        code: 'STRATEGY_MISMATCH',
        severity: 'warning',
        title: 'Does not match any declared strategy',
        message: 'Short TSLA on 1Min timeframe does not match any active strategy definition.',
        evidence: [],
      },
    ],
    all_items: [
      {
        evaluator: 'risk_positioning',
        code: 'NO_STOP_LOSS',
        severity: 'critical',
        title: 'No stop loss defined',
        message: 'This trade has no stop loss. Risk preferences require a stop loss on every trade.',
        evidence: [
          { metric_name: 'stop_loss_defined', value: 0, threshold: 1, comparison: '<', unit: 'boolean' },
        ],
      },
      {
        evaluator: 'risk_positioning',
        code: 'OVERSIZED_POSITION',
        severity: 'warning',
        title: 'Position size exceeds guidelines',
        message: 'Position represents 4.2% of account, exceeding the 2% max risk per trade guideline.',
        evidence: [
          { metric_name: 'position_risk_pct', value: 4.2, threshold: 2.0, comparison: '>', unit: '%' },
        ],
      },
      {
        evaluator: 'strategy_consistency',
        code: 'STRATEGY_MISMATCH',
        severity: 'warning',
        title: 'Does not match any declared strategy',
        message: 'Short TSLA on 1Min timeframe does not match any active strategy definition.',
        evidence: [],
      },
      {
        evaluator: 'regime_fit',
        code: 'REGIME_NEUTRAL',
        severity: 'info',
        title: 'Regime is neutral',
        message: 'Market regime is sideways consolidation. No strong directional bias.',
        evidence: [
          { metric_name: 'regime_label', value: 1, threshold: null, comparison: null, unit: null },
        ],
      },
      {
        evaluator: 'entry_timing',
        code: 'ENTRY_OK',
        severity: 'info',
        title: 'Entry timing acceptable',
        message: 'Entry price is near a reasonable support/resistance level.',
        evidence: [],
      },
    ],
    counts: { info: 2, warning: 2, critical: 1, blocker: 0 },
    evaluators_run: ['regime_fit', 'entry_timing', 'exit_logic', 'risk_positioning', 'behavioral', 'strategy_consistency'],
    evaluated_at: '2025-01-19T11:01:00Z',
  },

  'trade-005': {
    score: 25,
    summary: 'Revenge trade pattern detected after previous loss. Entry during extreme volatility regime.',
    has_blockers: true,
    top_issues: [
      {
        evaluator: 'behavioral',
        code: 'REVENGE_TRADE',
        severity: 'blocker',
        title: 'Revenge trade pattern',
        message: 'This trade was proposed within 12 minutes of closing a losing position. This matches a revenge trading pattern.',
        evidence: [
          { metric_name: 'time_since_last_loss', value: 12, threshold: 30, comparison: '<', unit: 'minutes' },
          { metric_name: 'previous_trade_pnl', value: -230, threshold: 0, comparison: '<', unit: 'USD' },
        ],
      },
      {
        evaluator: 'regime_fit',
        code: 'EXTREME_VOLATILITY',
        severity: 'blocker',
        title: 'Extreme volatility regime',
        message: 'Current realized volatility is in the 95th percentile. Entry during extreme vol has historically poor outcomes.',
        evidence: [
          { metric_name: 'rv_60_percentile', value: 95, threshold: 85, comparison: '>', unit: 'percentile' },
          { metric_name: 'regime_label', value: 4, threshold: null, comparison: null, unit: null },
        ],
      },
    ],
    all_items: [
      {
        evaluator: 'behavioral',
        code: 'REVENGE_TRADE',
        severity: 'blocker',
        title: 'Revenge trade pattern',
        message: 'This trade was proposed within 12 minutes of closing a losing position.',
        evidence: [
          { metric_name: 'time_since_last_loss', value: 12, threshold: 30, comparison: '<', unit: 'minutes' },
          { metric_name: 'previous_trade_pnl', value: -230, threshold: 0, comparison: '<', unit: 'USD' },
        ],
      },
      {
        evaluator: 'regime_fit',
        code: 'EXTREME_VOLATILITY',
        severity: 'blocker',
        title: 'Extreme volatility regime',
        message: 'Current realized volatility is in the 95th percentile.',
        evidence: [
          { metric_name: 'rv_60_percentile', value: 95, threshold: 85, comparison: '>', unit: 'percentile' },
        ],
      },
      {
        evaluator: 'risk_positioning',
        code: 'RISK_OK',
        severity: 'info',
        title: 'Risk sizing acceptable',
        message: 'Position risk is within limits.',
        evidence: [
          { metric_name: 'position_risk_pct', value: 1.7, threshold: 2.0, comparison: '<', unit: '%' },
        ],
      },
      {
        evaluator: 'exit_logic',
        code: 'EXIT_OK',
        severity: 'info',
        title: 'Exit logic defined',
        message: 'Stop and target are set.',
        evidence: [
          { metric_name: 'risk_reward_ratio', value: 1.67, threshold: 1.5, comparison: '>=', unit: null },
        ],
      },
    ],
    counts: { info: 2, warning: 0, critical: 0, blocker: 2 },
    evaluators_run: ['regime_fit', 'entry_timing', 'exit_logic', 'risk_positioning', 'behavioral', 'strategy_consistency'],
    evaluated_at: '2025-01-22T10:01:00Z',
  },

  'trade-006': {
    score: 48,
    summary: 'Trade goes against declared long-only strategy. Otherwise acceptable setup.',
    has_blockers: false,
    top_issues: [
      {
        evaluator: 'strategy_consistency',
        code: 'DIRECTION_MISMATCH',
        severity: 'critical',
        title: 'Against declared strategy direction',
        message: 'Your active strategies are all long-only, but this is a short trade. This is a deviation from your declared approach.',
        evidence: [
          { metric_name: 'declared_direction', value: 0, threshold: null, comparison: null, unit: 'long' },
          { metric_name: 'trade_direction', value: 1, threshold: null, comparison: null, unit: 'short' },
        ],
      },
    ],
    all_items: [
      {
        evaluator: 'strategy_consistency',
        code: 'DIRECTION_MISMATCH',
        severity: 'critical',
        title: 'Against declared strategy direction',
        message: 'Your active strategies are all long-only, but this is a short trade.',
        evidence: [
          { metric_name: 'declared_direction', value: 0, threshold: null, comparison: null, unit: 'long' },
          { metric_name: 'trade_direction', value: 1, threshold: null, comparison: null, unit: 'short' },
        ],
      },
      {
        evaluator: 'regime_fit',
        code: 'REGIME_OK',
        severity: 'info',
        title: 'Regime is compatible',
        message: 'Current regime supports short entries.',
        evidence: [],
      },
      {
        evaluator: 'risk_positioning',
        code: 'RISK_OK',
        severity: 'info',
        title: 'Risk sizing acceptable',
        message: 'Position risk within limits.',
        evidence: [
          { metric_name: 'position_risk_pct', value: 1.0, threshold: 2.0, comparison: '<', unit: '%' },
        ],
      },
      {
        evaluator: 'exit_logic',
        code: 'EXIT_OK',
        severity: 'info',
        title: 'Exit plan is solid',
        message: 'R:R of 3.0 exceeds minimum.',
        evidence: [
          { metric_name: 'risk_reward_ratio', value: 3.0, threshold: 1.5, comparison: '>=', unit: null },
        ],
      },
    ],
    counts: { info: 3, warning: 0, critical: 1, blocker: 0 },
    evaluators_run: ['regime_fit', 'entry_timing', 'exit_logic', 'risk_positioning', 'behavioral', 'strategy_consistency'],
    evaluated_at: '2025-01-18T13:01:00Z',
  },
};
