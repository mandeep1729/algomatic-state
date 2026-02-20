/**
 * Single condition row in the builder — renders the appropriate inputs
 * based on the selected operator.
 */

import { X } from 'lucide-react';
import type { ConditionNode, ConditionRef } from './conditionTypes';
import {
  OPERATORS,
  INDICATORS,
  INDICATOR_GROUP_LABELS,
  CATEGORY_LABELS,
  OPERATOR_MAP,
} from './conditionMeta';
import { GroupedSelect } from './GroupedSelect';

interface ConditionRowProps {
  node: ConditionNode;
  onChange: (updated: ConditionNode) => void;
  onRemove: () => void;
}

// Build grouped option lists once
const indicatorOptions = INDICATORS.map((i) => ({
  value: i.col,
  label: i.label,
  group: i.group,
}));

const operatorOptions = OPERATORS.map((o) => ({
  value: o.op,
  label: o.label,
  group: o.category,
}));

export function ConditionRow({ node, onChange, onRemove }: ConditionRowProps) {
  const opMeta = OPERATOR_MAP.get(node.op);
  const needs = new Set(opMeta?.requiredFields ?? []);

  function updateOp(op: string) {
    // When switching operator, reset fields to avoid stale data
    const fresh: ConditionNode = { op };
    // Carry over col if new op also uses col
    const newMeta = OPERATOR_MAP.get(op);
    const newNeeds = new Set(newMeta?.requiredFields ?? []);
    if (newNeeds.has('col') && node.col) fresh.col = node.col;
    if (newNeeds.has('ref') && node.ref) fresh.ref = node.ref;
    onChange(fresh);
  }

  function updateCol(col: string) {
    onChange({ ...node, col });
  }

  function updateRef(ref: ConditionRef) {
    onChange({ ...node, ref });
  }

  function updateNum(field: keyof ConditionNode, value: string) {
    const num = value === '' ? undefined : parseFloat(value);
    onChange({ ...node, [field]: num });
  }

  function updateStr(field: keyof ConditionNode, value: string) {
    onChange({ ...node, [field]: value || undefined });
  }

  return (
    <div className="flex flex-wrap items-center gap-1.5 rounded-md border border-[var(--border-color)] bg-[var(--bg-primary)] px-2 py-1.5">
      {/* Col selector (for comparison, directional, held, deviation ops) */}
      {needs.has('col') && (
        <GroupedSelect
          value={node.col ?? ''}
          onChange={updateCol}
          options={indicatorOptions}
          groupLabels={INDICATOR_GROUP_LABELS}
          className="w-28"
        />
      )}

      {/* Operator selector */}
      <GroupedSelect
        value={node.op}
        onChange={updateOp}
        options={operatorOptions}
        groupLabels={CATEGORY_LABELS}
        className="w-44"
      />

      {/* Ref: either column or value */}
      {needs.has('ref') && (
        <RefInput
          ref_={node.ref}
          onChange={updateRef}
        />
      )}

      {/* N parameter */}
      {needs.has('n') && (
        <span className="flex items-center gap-1 text-xs text-[var(--text-secondary)]">
          over
          <input
            type="number"
            value={node.n ?? ''}
            onChange={(e) => updateNum('n', e.target.value)}
            className="form-input h-7 w-14 text-xs"
            min={1}
          />
          bars
        </span>
      )}

      {/* Threshold */}
      {needs.has('threshold') && (
        <input
          type="number"
          value={node.threshold ?? ''}
          onChange={(e) => updateNum('threshold', e.target.value)}
          className="form-input h-7 w-20 text-xs"
          placeholder="threshold"
          step={0.1}
        />
      )}

      {/* Lookback (for divergence, squeeze, was_*) */}
      {needs.has('lookback') && (
        <span className="flex items-center gap-1 text-xs text-[var(--text-secondary)]">
          lookback
          <input
            type="number"
            value={node.lookback ?? ''}
            onChange={(e) => updateNum('lookback', e.target.value)}
            className="form-input h-7 w-14 text-xs"
            min={1}
          />
        </span>
      )}

      {/* Multiplier (range_exceeds_atr) */}
      {needs.has('multiplier') && (
        <span className="flex items-center gap-1 text-xs text-[var(--text-secondary)]">
          <input
            type="number"
            value={node.multiplier ?? ''}
            onChange={(e) => updateNum('multiplier', e.target.value)}
            className="form-input h-7 w-16 text-xs"
            step={0.1}
          />
          x
        </span>
      )}

      {/* Level col (pullback, breakout) */}
      {needs.has('level_col') && (
        <GroupedSelect
          value={node.level_col ?? ''}
          onChange={(v) => updateStr('level_col', v)}
          options={indicatorOptions}
          groupLabels={INDICATOR_GROUP_LABELS}
          className="w-28"
          placeholder="level..."
        />
      )}

      {/* Indicator col (divergence) */}
      {needs.has('indicator_col') && (
        <GroupedSelect
          value={node.indicator_col ?? ''}
          onChange={(v) => updateStr('indicator_col', v)}
          options={indicatorOptions}
          groupLabels={INDICATOR_GROUP_LABELS}
          className="w-28"
          placeholder="indicator..."
        />
      )}

      {/* Pattern col (candle) */}
      {needs.has('pattern_col') && (
        <input
          type="text"
          value={node.pattern_col ?? ''}
          onChange={(e) => updateStr('pattern_col', e.target.value)}
          className="form-input h-7 w-28 text-xs"
          placeholder="pattern col..."
        />
      )}

      {/* Width col (squeeze) */}
      {needs.has('width_col') && (
        <GroupedSelect
          value={node.width_col ?? ''}
          onChange={(v) => updateStr('width_col', v)}
          options={indicatorOptions}
          groupLabels={INDICATOR_GROUP_LABELS}
          className="w-28"
          placeholder="width..."
        />
      )}

      {/* Ref col (deviation) */}
      {needs.has('ref_col') && (
        <GroupedSelect
          value={node.ref_col ?? ''}
          onChange={(v) => updateStr('ref_col', v)}
          options={indicatorOptions}
          groupLabels={INDICATOR_GROUP_LABELS}
          className="w-28"
          placeholder="ref col..."
        />
      )}

      {/* ATR mult (gap, deviation) */}
      {needs.has('atr_mult') && (
        <span className="flex items-center gap-1 text-xs text-[var(--text-secondary)]">
          <input
            type="number"
            value={node.atr_mult ?? ''}
            onChange={(e) => updateNum('atr_mult', e.target.value)}
            className="form-input h-7 w-16 text-xs"
            step={0.1}
          />
          x ATR
        </span>
      )}

      {/* Low / High (adx_in_range) */}
      {needs.has('low') && (
        <span className="flex items-center gap-1 text-xs text-[var(--text-secondary)]">
          <input
            type="number"
            value={node.low ?? ''}
            onChange={(e) => updateNum('low', e.target.value)}
            className="form-input h-7 w-16 text-xs"
            placeholder="low"
          />
          -
          <input
            type="number"
            value={node.high ?? ''}
            onChange={(e) => updateNum('high', e.target.value)}
            className="form-input h-7 w-16 text-xs"
            placeholder="high"
          />
        </span>
      )}

      {/* Remove button */}
      <button
        type="button"
        onClick={onRemove}
        className="ml-auto rounded p-0.5 text-[var(--text-secondary)] hover:text-[var(--accent-red)]"
        title="Remove condition"
      >
        <X size={14} />
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Ref Input — toggle between column and numeric value
// ---------------------------------------------------------------------------

function RefInput({
  ref_,
  onChange,
}: {
  ref_?: ConditionRef;
  onChange: (ref: ConditionRef) => void;
}) {
  const isCol = Boolean(ref_?.col);

  return (
    <span className="flex items-center gap-1">
      <button
        type="button"
        onClick={() => {
          if (isCol) {
            onChange({ value: 0 });
          } else {
            onChange({ col: 'ema_20' });
          }
        }}
        className="rounded border border-[var(--border-color)] px-1.5 py-0.5 text-[10px] text-[var(--text-secondary)] hover:text-[var(--accent-blue)]"
        title={isCol ? 'Switch to numeric value' : 'Switch to column reference'}
      >
        {isCol ? 'Col' : 'Val'}
      </button>
      {isCol ? (
        <GroupedSelect
          value={ref_?.col ?? ''}
          onChange={(col) => onChange({ col })}
          options={indicatorOptions}
          groupLabels={INDICATOR_GROUP_LABELS}
          className="w-28"
        />
      ) : (
        <input
          type="number"
          value={ref_?.value ?? ''}
          onChange={(e) =>
            onChange({ value: e.target.value === '' ? undefined : parseFloat(e.target.value) })
          }
          className="form-input h-7 w-20 text-xs"
          placeholder="value"
          step={0.1}
        />
      )}
    </span>
  );
}
