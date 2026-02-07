import { useState } from 'react';
import type { EvaluationDimension } from '../../types';
import { SeverityBadge } from './SeverityBadge';

interface EvaluationCardProps {
  dimension: EvaluationDimension;
  defaultOpen?: boolean;
}

const DIMENSION_LABELS: Record<string, string> = {
  regime_fit: 'Regime Fit',
  entry_timing: 'Entry Timing',
  exit_logic: 'Exit Logic',
  risk_structure: 'Risk Structure',
  behavioral: 'Behavioral',
  strategy_consistency: 'Strategy Consistency',
};

export function EvaluationCard({ dimension, defaultOpen = false }: EvaluationCardProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  const dimensionLabel =
    DIMENSION_LABELS[dimension.dimensionKey] ??
    dimension.dimensionKey.replace(/_/g, ' ');

  return (
    <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)]">
      {/* Header -- clickable to expand/collapse */}
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        className="flex w-full items-start justify-between gap-3 p-4 text-left"
      >
        <div className="min-w-0">
          <div className="text-sm font-medium text-[var(--text-primary)]">
            {dimension.label}
          </div>
          <div className="mt-0.5 text-xs text-[var(--text-secondary)]">
            {dimensionLabel}
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <SeverityBadge severity={dimension.severity} />
          <svg
            className={`h-4 w-4 text-[var(--text-secondary)] transition-transform ${
              isOpen ? 'rotate-180' : ''
            }`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </button>

      {/* Expandable body */}
      {isOpen && (
        <div className="border-t border-[var(--border-color)] px-4 pb-4 pt-3">
          <p className="text-sm text-[var(--text-secondary)]">{dimension.explanation}</p>

          {dimension.visuals && Object.keys(dimension.visuals).length > 0 && (
            <div className="mt-3 rounded-md border border-[var(--border-color)] bg-[var(--bg-primary)] p-3">
              <div className="mb-1 text-xs font-medium text-[var(--text-secondary)]">
                Visuals
              </div>
              <pre className="overflow-x-auto text-xs text-[var(--text-secondary)]">
                {JSON.stringify(dimension.visuals, null, 2)}
              </pre>
            </div>
          )}

          {dimension.evidence && Object.keys(dimension.evidence).length > 0 && (
            <details className="mt-3">
              <summary className="cursor-pointer text-xs font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)]">
                Evidence
              </summary>
              <pre className="mt-2 overflow-x-auto rounded-md border border-[var(--border-color)] bg-[var(--bg-primary)] p-3 text-xs text-[var(--text-secondary)]">
                {JSON.stringify(dimension.evidence, null, 2)}
              </pre>
            </details>
          )}
        </div>
      )}
    </div>
  );
}
