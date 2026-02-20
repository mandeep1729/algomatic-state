/**
 * Operator and indicator registries for the condition builder UI.
 *
 * These registries drive the dropdown options in ConditionRow
 * and generate human-readable previews in ConditionSummary.
 */

import type { OperatorMeta, IndicatorMeta, OperatorCategory } from './conditionTypes';

// ---------------------------------------------------------------------------
// Operators
// ---------------------------------------------------------------------------

export const OPERATORS: OperatorMeta[] = [
  // Comparison
  { op: 'crosses_above', label: 'crosses above', category: 'comparison', requiredFields: ['col', 'ref'], descriptionTemplate: '{col} crosses above {ref}' },
  { op: 'crosses_below', label: 'crosses below', category: 'comparison', requiredFields: ['col', 'ref'], descriptionTemplate: '{col} crosses below {ref}' },
  { op: 'above', label: 'above', category: 'comparison', requiredFields: ['col', 'ref'], descriptionTemplate: '{col} above {ref}' },
  { op: 'below', label: 'below', category: 'comparison', requiredFields: ['col', 'ref'], descriptionTemplate: '{col} below {ref}' },

  // Directional
  { op: 'rising', label: 'rising', category: 'directional', requiredFields: ['col', 'n'], descriptionTemplate: '{col} rising over {n} bars' },
  { op: 'falling', label: 'falling', category: 'directional', requiredFields: ['col', 'n'], descriptionTemplate: '{col} falling over {n} bars' },

  // Pullback
  { op: 'pullback_to', label: 'pullback to', category: 'pullback', requiredFields: ['level_col'], descriptionTemplate: 'pullback to {level_col}' },

  // Divergence
  { op: 'bullish_divergence', label: 'bullish divergence', category: 'divergence', requiredFields: ['indicator_col'], descriptionTemplate: 'bullish divergence on {indicator_col}' },
  { op: 'bearish_divergence', label: 'bearish divergence', category: 'divergence', requiredFields: ['indicator_col'], descriptionTemplate: 'bearish divergence on {indicator_col}' },

  // Candle
  { op: 'candle_bullish', label: 'bullish candle', category: 'candle', requiredFields: ['pattern_col'], descriptionTemplate: 'bullish {pattern_col}' },
  { op: 'candle_bearish', label: 'bearish candle', category: 'candle', requiredFields: ['pattern_col'], descriptionTemplate: 'bearish {pattern_col}' },

  // Breakout
  { op: 'breaks_above_level', label: 'breaks above level', category: 'breakout', requiredFields: ['level_col'], descriptionTemplate: 'breaks above {level_col}' },
  { op: 'breaks_below_level', label: 'breaks below level', category: 'breakout', requiredFields: ['level_col'], descriptionTemplate: 'breaks below {level_col}' },

  // Volatility
  { op: 'squeeze', label: 'squeeze', category: 'volatility', requiredFields: ['width_col'], descriptionTemplate: '{width_col} squeeze (lookback {lookback})' },
  { op: 'range_exceeds_atr', label: 'range exceeds ATR', category: 'volatility', requiredFields: ['multiplier'], descriptionTemplate: 'range exceeds {multiplier}x ATR' },
  { op: 'bb_width_increasing', label: 'BB width increasing', category: 'volatility', requiredFields: ['n'], descriptionTemplate: 'BB width increasing over {n} bars' },

  // Gap
  { op: 'gap_up', label: 'gap up', category: 'gap', requiredFields: ['atr_mult'], descriptionTemplate: 'gap up > {atr_mult}x ATR' },
  { op: 'gap_down', label: 'gap down', category: 'gap', requiredFields: ['atr_mult'], descriptionTemplate: 'gap down > {atr_mult}x ATR' },

  // Holding / state
  { op: 'held_above', label: 'held above', category: 'holding', requiredFields: ['col', 'threshold', 'n'], descriptionTemplate: '{col} held above {threshold} for {n} bars' },
  { op: 'held_below', label: 'held below', category: 'holding', requiredFields: ['col', 'threshold', 'n'], descriptionTemplate: '{col} held below {threshold} for {n} bars' },
  { op: 'was_below_then_crosses_above', label: 'was below then crosses above', category: 'holding', requiredFields: ['col', 'threshold'], descriptionTemplate: '{col} was below {threshold} then crosses above' },
  { op: 'was_above_then_crosses_below', label: 'was above then crosses below', category: 'holding', requiredFields: ['col', 'threshold'], descriptionTemplate: '{col} was above {threshold} then crosses below' },

  // Range
  { op: 'adx_in_range', label: 'ADX in range', category: 'range', requiredFields: ['low', 'high'], descriptionTemplate: 'ADX between {low} and {high}' },
  { op: 'deviation_below', label: 'deviation below', category: 'range', requiredFields: ['col', 'ref_col', 'atr_mult'], descriptionTemplate: '{col} deviates below {ref_col} by {atr_mult}x ATR' },
  { op: 'deviation_above', label: 'deviation above', category: 'range', requiredFields: ['col', 'ref_col', 'atr_mult'], descriptionTemplate: '{col} deviates above {ref_col} by {atr_mult}x ATR' },
];

/** Lookup operator metadata by op string. */
export const OPERATOR_MAP = new Map(OPERATORS.map(o => [o.op, o]));

/** Category labels for grouped display. */
export const CATEGORY_LABELS: Record<OperatorCategory, string> = {
  comparison: 'Comparison',
  directional: 'Directional',
  composite: 'Composite',
  pullback: 'Pullback',
  divergence: 'Divergence',
  candle: 'Candlestick',
  breakout: 'Breakout',
  volatility: 'Volatility',
  gap: 'Gap',
  holding: 'Holding / State',
  range: 'Range / ADX',
};

// ---------------------------------------------------------------------------
// Indicators
// ---------------------------------------------------------------------------

export const INDICATORS: IndicatorMeta[] = [
  // Price
  { col: 'open', label: 'Open', group: 'price' },
  { col: 'high', label: 'High', group: 'price' },
  { col: 'low', label: 'Low', group: 'price' },
  { col: 'close', label: 'Close', group: 'price' },
  { col: 'volume', label: 'Volume', group: 'volume' },

  // Moving averages
  { col: 'ema_9', label: 'EMA 9', group: 'moving_average' },
  { col: 'ema_20', label: 'EMA 20', group: 'moving_average' },
  { col: 'ema_50', label: 'EMA 50', group: 'moving_average' },
  { col: 'sma_20', label: 'SMA 20', group: 'moving_average' },
  { col: 'sma_50', label: 'SMA 50', group: 'moving_average' },
  { col: 'sma_200', label: 'SMA 200', group: 'moving_average' },
  { col: 'vwap', label: 'VWAP', group: 'moving_average' },

  // Oscillators
  { col: 'rsi_14', label: 'RSI 14', group: 'oscillator' },
  { col: 'macd_line', label: 'MACD Line', group: 'oscillator' },
  { col: 'macd_signal', label: 'MACD Signal', group: 'oscillator' },
  { col: 'macd_hist', label: 'MACD Histogram', group: 'oscillator' },
  { col: 'stoch_k', label: 'Stochastic %K', group: 'oscillator' },
  { col: 'stoch_d', label: 'Stochastic %D', group: 'oscillator' },
  { col: 'cci_20', label: 'CCI 20', group: 'oscillator' },
  { col: 'willr_14', label: 'Williams %R 14', group: 'oscillator' },
  { col: 'trix_15', label: 'TRIX 15', group: 'oscillator' },

  // Volatility
  { col: 'atr_14', label: 'ATR 14', group: 'volatility' },
  { col: 'bb_upper', label: 'BB Upper', group: 'volatility' },
  { col: 'bb_middle', label: 'BB Middle', group: 'volatility' },
  { col: 'bb_lower', label: 'BB Lower', group: 'volatility' },
  { col: 'bb_width', label: 'BB Width', group: 'volatility' },
  { col: 'kc_upper', label: 'KC Upper', group: 'volatility' },
  { col: 'kc_lower', label: 'KC Lower', group: 'volatility' },

  // Trend strength
  { col: 'adx_14', label: 'ADX 14', group: 'other' },
  { col: 'plus_di', label: '+DI', group: 'other' },
  { col: 'minus_di', label: '-DI', group: 'other' },

  // Volume indicators
  { col: 'obv', label: 'OBV', group: 'volume' },
  { col: 'cmf_20', label: 'CMF 20', group: 'volume' },
  { col: 'volume_sma_20', label: 'Volume SMA 20', group: 'volume' },
];

/** Lookup indicator metadata by column name. */
export const INDICATOR_MAP = new Map(INDICATORS.map(i => [i.col, i]));

/** Group labels for indicator dropdowns. */
export const INDICATOR_GROUP_LABELS: Record<IndicatorMeta['group'], string> = {
  price: 'Price',
  moving_average: 'Moving Averages',
  oscillator: 'Oscillators',
  volatility: 'Volatility',
  volume: 'Volume',
  pattern: 'Patterns',
  other: 'Other',
};
