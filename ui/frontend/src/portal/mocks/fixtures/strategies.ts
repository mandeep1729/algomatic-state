import type { StrategyDefinition, EvaluationControls } from '../../types';

export const MOCK_STRATEGIES: StrategyDefinition[] = [
  {
    id: 'strategy-001',
    name: 'Momentum Pullback Long',
    description: 'Enter long on a pullback to VWAP or EMA during an uptrending regime. Wait for confirmation on 5-minute chart.',
    direction: 'long',
    timeframes: ['15Min', '1Hour'],
    entry_criteria: 'Pullback to VWAP or EMA-48 with volume confirmation, in an uptrending regime.',
    exit_criteria: 'Stop loss at swing low or 2% max loss. Target at next resistance or 2:1 R:R.',
    max_risk_pct: 2.0,
    min_risk_reward: 2.0,
    is_active: true,
  },
  {
    id: 'strategy-002',
    name: 'Breakout Scalp',
    description: 'Quick scalp on intraday breakouts above 20-bar high with volume surge.',
    direction: 'long',
    timeframes: ['1Min', '15Min'],
    entry_criteria: 'Price breaks above 20-bar high with relative volume > 2x. Enter on first pullback after breakout.',
    exit_criteria: 'Tight stop at breakout level. Target 1:1 to 1.5:1 R:R. Time stop: exit if no follow-through within 15 minutes.',
    max_risk_pct: 1.0,
    min_risk_reward: 1.5,
    is_active: true,
  },
];

export const MOCK_EVALUATION_CONTROLS: EvaluationControls = {
  evaluators_enabled: {
    regime_fit: true,
    entry_timing: true,
    exit_logic: true,
    risk_positioning: true,
    behavioral: true,
    strategy_consistency: true,
  },
  auto_evaluate_synced: true,
  notification_on_blocker: true,
  severity_threshold: 'warning',
};
