/**
 * Utility functions for condition nodes: serialization, text rendering, feature extraction.
 */

import type { ConditionNode, ConditionRef } from './conditionTypes';
import { OPERATOR_MAP, INDICATOR_MAP } from './conditionMeta';

// ---------------------------------------------------------------------------
// Factory helpers
// ---------------------------------------------------------------------------

/** Create a fresh empty leaf condition node. */
export function createEmptyLeaf(): ConditionNode {
  return { op: 'above', col: 'close', ref: { value: 0 } };
}

/** Create a ref from a column name. */
export function colRef(col: string): ConditionRef {
  return { col };
}

/** Create a ref from a numeric value. */
export function numRef(value: number): ConditionRef {
  return { value };
}

// ---------------------------------------------------------------------------
// Type guards
// ---------------------------------------------------------------------------

/** True if the node is a composite (all_of / any_of). */
export function isComposite(node: ConditionNode): boolean {
  return node.op === 'all_of' || node.op === 'any_of';
}

/** True if the node uses col + ref pattern. */
export function isComparison(node: ConditionNode): boolean {
  return ['crosses_above', 'crosses_below', 'above', 'below'].includes(node.op);
}

// ---------------------------------------------------------------------------
// Text rendering
// ---------------------------------------------------------------------------

/** Render a ConditionRef as human-readable text. */
function refToText(ref: ConditionRef | undefined): string {
  if (!ref) return '?';
  if (ref.col) {
    const meta = INDICATOR_MAP.get(ref.col);
    return meta ? meta.label : ref.col;
  }
  if (ref.value !== undefined) return String(ref.value);
  return '?';
}

/** Render a column name as human-readable text. */
function colToText(col: string | undefined): string {
  if (!col) return '?';
  const meta = INDICATOR_MAP.get(col);
  return meta ? meta.label : col;
}

/** Convert a single ConditionNode to human-readable text. */
export function conditionToText(node: ConditionNode): string {
  const opMeta = OPERATOR_MAP.get(node.op);
  if (!opMeta) return `[unknown: ${node.op}]`;

  let text = opMeta.descriptionTemplate;

  // Replace placeholders with actual values
  text = text.replace('{col}', colToText(node.col));
  text = text.replace('{ref}', refToText(node.ref));
  text = text.replace('{n}', String(node.n ?? ''));
  text = text.replace('{threshold}', String(node.threshold ?? ''));
  text = text.replace('{lookback}', String(node.lookback ?? ''));
  text = text.replace('{multiplier}', String(node.multiplier ?? ''));
  text = text.replace('{level_col}', colToText(node.level_col));
  text = text.replace('{indicator_col}', colToText(node.indicator_col));
  text = text.replace('{pattern_col}', colToText(node.pattern_col));
  text = text.replace('{width_col}', colToText(node.width_col));
  text = text.replace('{ref_col}', colToText(node.ref_col));
  text = text.replace('{atr_mult}', String(node.atr_mult ?? ''));
  text = text.replace('{low}', String(node.low ?? ''));
  text = text.replace('{high}', String(node.high ?? ''));

  return text;
}

/** Convert an array of condition nodes to a human-readable summary. */
export function conditionsToText(nodes: ConditionNode[], joiner: 'AND' | 'OR' = 'AND'): string {
  if (!nodes || nodes.length === 0) return '(none)';
  return nodes.map(conditionToText).join(` ${joiner} `);
}

// ---------------------------------------------------------------------------
// Feature extraction
// ---------------------------------------------------------------------------

/** Walk condition tree and collect all referenced indicator column names. */
export function extractFeatures(nodes: ConditionNode[]): string[] {
  const seen = new Set<string>();

  function walk(node: ConditionNode) {
    if (node.col) seen.add(node.col);
    if (node.ref?.col) seen.add(node.ref.col);
    if (node.level_col) seen.add(node.level_col);
    if (node.indicator_col) seen.add(node.indicator_col);
    if (node.pattern_col) seen.add(node.pattern_col);
    if (node.width_col) seen.add(node.width_col);
    if (node.ref_col) seen.add(node.ref_col);

    // Implicit ATR dependency
    if (['pullback_to', 'range_exceeds_atr', 'gap_up', 'gap_down', 'deviation_below', 'deviation_above'].includes(node.op)) {
      seen.add('atr_14');
    }
    if (node.op === 'adx_in_range') seen.add('adx_14');
    if (node.op === 'bb_width_increasing') seen.add('bb_width');

    node.conditions?.forEach(walk);
  }

  nodes.forEach(walk);

  // Filter out raw OHLCV — those aren't computed features
  const ohlcv = new Set(['open', 'high', 'low', 'close', 'volume']);
  return Array.from(seen).filter(col => !ohlcv.has(col));
}

// ---------------------------------------------------------------------------
// Serialization
// ---------------------------------------------------------------------------

/** Try to parse a string as structured DSL conditions. Returns null if it's plain text. */
export function parseConditions(value: string | null | undefined): ConditionNode[] | null {
  if (!value) return null;
  try {
    const parsed = JSON.parse(value);
    if (Array.isArray(parsed) && parsed.length > 0 && parsed[0]?.op) {
      return parsed as ConditionNode[];
    }
  } catch {
    // Not JSON — legacy plain text
  }
  return null;
}

/** Serialize condition nodes to a JSON string for storage. */
export function serializeConditions(nodes: ConditionNode[]): string {
  if (!nodes || nodes.length === 0) return '';
  // Strip undefined/empty optional fields for cleaner storage
  const clean = nodes.map(stripEmpty);
  return JSON.stringify(clean);
}

/** Remove undefined and empty optional fields from a condition node. */
function stripEmpty(node: ConditionNode): Record<string, unknown> {
  const result: Record<string, unknown> = { op: node.op };

  if (node.col) result.col = node.col;
  if (node.ref) {
    const ref: Record<string, unknown> = {};
    if (node.ref.col) ref.col = node.ref.col;
    if (node.ref.value !== undefined) ref.value = node.ref.value;
    result.ref = ref;
  }
  if (node.n !== undefined && node.n > 0) result.n = node.n;
  if (node.threshold !== undefined && node.threshold !== 0) result.threshold = node.threshold;
  if (node.lookback !== undefined && node.lookback > 0) result.lookback = node.lookback;
  if (node.multiplier !== undefined && node.multiplier !== 0) result.multiplier = node.multiplier;
  if (node.level_col) result.level_col = node.level_col;
  if (node.tolerance_atr_mult !== undefined) result.tolerance_atr_mult = node.tolerance_atr_mult;
  if (node.indicator_col) result.indicator_col = node.indicator_col;
  if (node.pattern_col) result.pattern_col = node.pattern_col;
  if (node.width_col) result.width_col = node.width_col;
  if (node.ref_col) result.ref_col = node.ref_col;
  if (node.atr_mult !== undefined && node.atr_mult !== 0) result.atr_mult = node.atr_mult;
  if (node.low !== undefined) result.low = node.low;
  if (node.high !== undefined) result.high = node.high;
  if (node.conditions && node.conditions.length > 0) {
    result.conditions = node.conditions.map(stripEmpty);
  }

  return result;
}
