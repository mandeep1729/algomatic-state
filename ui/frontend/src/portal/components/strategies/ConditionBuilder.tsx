/**
 * Main condition builder for one condition slot (e.g. "Entry Long").
 *
 * Manages an array of ConditionNode objects — renders ConditionRow for each,
 * plus an "Add Rule" button and a summary preview.
 */

import { Plus } from 'lucide-react';
import type { ConditionNode } from './conditionTypes';
import { createEmptyLeaf, parseConditions, serializeConditions, extractFeatures } from './conditionUtils';
import { ConditionRow } from './ConditionRow';
import { ConditionSummary } from './ConditionSummary';

interface ConditionBuilderProps {
  /** Slot label, e.g. "Entry Long". */
  label: string;
  /** Current serialized value (JSON string or plain text). */
  value: string | null;
  /** Called with updated JSON string on changes. */
  onChange: (value: string | null) => void;
  /** How conditions are joined for preview. Entry=AND, Exit=OR. */
  joiner?: 'AND' | 'OR';
  /** Callback to propagate extracted features to the parent. */
  onFeaturesChange?: (features: string[]) => void;
}

export function ConditionBuilder({
  label,
  value,
  onChange,
  joiner = 'AND',
  onFeaturesChange,
}: ConditionBuilderProps) {
  // Parse current value into structured nodes
  const structured = parseConditions(value);
  const isLegacy = value != null && value.trim() !== '' && structured === null;
  const nodes: ConditionNode[] = structured ?? [];

  function emitChange(updated: ConditionNode[]) {
    if (updated.length === 0) {
      onChange(null);
    } else {
      onChange(serializeConditions(updated));
    }
    onFeaturesChange?.(extractFeatures(updated));
  }

  function addRule() {
    emitChange([...nodes, createEmptyLeaf()]);
  }

  function updateRule(index: number, updated: ConditionNode) {
    const copy = [...nodes];
    copy[index] = updated;
    emitChange(copy);
  }

  function removeRule(index: number) {
    emitChange(nodes.filter((_, i) => i !== index));
  }

  // Legacy plain-text fallback
  if (isLegacy) {
    return (
      <div className="space-y-1">
        <div className="flex items-center justify-between">
          <label className="text-xs font-medium text-[var(--text-secondary)]">{label}</label>
          <span className="text-[10px] italic text-[var(--text-tertiary)]">Plain text (read-only)</span>
        </div>
        <div className="rounded-md border border-[var(--border-color)] bg-[var(--bg-primary)] px-2 py-1.5 text-xs text-[var(--text-secondary)] whitespace-pre-wrap">
          {value}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-1.5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <label className="text-xs font-medium text-[var(--text-secondary)]">{label}</label>
        <button
          type="button"
          onClick={addRule}
          className="inline-flex items-center gap-1 rounded border border-[var(--border-color)] px-2 py-0.5 text-[10px] text-[var(--text-secondary)] hover:text-[var(--accent-blue)] hover:border-[var(--accent-blue)]"
        >
          <Plus size={10} /> Add Rule
        </button>
      </div>

      {/* Condition rows */}
      {nodes.length === 0 ? (
        <div className="rounded-md border border-dashed border-[var(--border-color)] px-3 py-2 text-center text-[11px] text-[var(--text-tertiary)]">
          No conditions — click Add Rule to begin
        </div>
      ) : (
        <div className="space-y-1">
          {nodes.map((node, i) => (
            <ConditionRow
              key={i}
              node={node}
              onChange={(updated) => updateRule(i, updated)}
              onRemove={() => removeRule(i)}
            />
          ))}
        </div>
      )}

      {/* Summary preview */}
      {nodes.length > 0 && (
        <div className="rounded-md border border-[var(--border-color)] bg-[var(--bg-primary)] px-2 py-1">
          <ConditionSummary conditions={nodes} joiner={joiner} />
        </div>
      )}
    </div>
  );
}
