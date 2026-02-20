/**
 * TypeScript types for the JSON condition DSL.
 *
 * These types mirror the Go `dsl.ConditionNode` struct and define
 * the shape of conditions stored in the JSONB columns of agent_strategies.
 */

/** Reference to either an indicator column or a literal number. */
export interface ConditionRef {
  col?: string;
  value?: number;
}

/**
 * A single condition node in the DSL tree.
 * The `op` field determines which other fields are relevant.
 */
export interface ConditionNode {
  op: string;

  // Comparison operators
  col?: string;
  ref?: ConditionRef;

  // Parameterized operators
  n?: number;
  threshold?: number;
  lookback?: number;
  multiplier?: number;

  // Named column fields
  level_col?: string;
  tolerance_atr_mult?: number;
  indicator_col?: string;
  pattern_col?: string;
  width_col?: string;
  ref_col?: string;
  atr_mult?: number;

  // ADX range
  low?: number;
  high?: number;

  // Composite operators
  conditions?: ConditionNode[];
}

/** Operator category for grouping in the UI dropdown. */
export type OperatorCategory =
  | 'comparison'
  | 'directional'
  | 'composite'
  | 'pullback'
  | 'divergence'
  | 'candle'
  | 'breakout'
  | 'volatility'
  | 'gap'
  | 'holding'
  | 'range';

/** Shape of an operator entry in the metadata registry. */
export interface OperatorMeta {
  op: string;
  label: string;
  category: OperatorCategory;
  /** Which ConditionNode fields this operator requires. */
  requiredFields: (keyof ConditionNode)[];
  /** Human-readable template, e.g. "{col} crosses above {ref}". */
  descriptionTemplate: string;
}

/** Shape of an indicator entry in the metadata registry. */
export interface IndicatorMeta {
  col: string;
  label: string;
  group: 'price' | 'moving_average' | 'oscillator' | 'volatility' | 'volume' | 'pattern' | 'other';
}
