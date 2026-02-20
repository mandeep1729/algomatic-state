/**
 * Read-only human-readable preview of a condition array.
 */

import type { ConditionNode } from './conditionTypes';
import { conditionsToText } from './conditionUtils';

interface ConditionSummaryProps {
  conditions: ConditionNode[];
  /** How entry conditions are joined (AND) vs exit (OR). */
  joiner?: 'AND' | 'OR';
}

export function ConditionSummary({ conditions, joiner = 'AND' }: ConditionSummaryProps) {
  if (!conditions || conditions.length === 0) {
    return (
      <p className="text-[11px] italic text-[var(--text-secondary)]">
        No conditions defined
      </p>
    );
  }

  return (
    <p className="text-[11px] text-[var(--text-secondary)]">
      {conditionsToText(conditions, joiner)}
    </p>
  );
}
