import { useState } from 'react';
import type { EvaluationResponse, EvaluationItemResponse, Severity } from '../types';
import { SeverityBadge, SeverityIcon } from './badges';

// Map evaluator codes to dimension labels
const DIMENSION_LABELS: Record<string, string> = {
  regime_fit: 'Regime Fit',
  entry_timing: 'Entry Timing',
  exit_logic: 'Exit Logic',
  risk_positioning: 'Risk & Positioning',
  behavioral: 'Behavioral Signals',
  strategy_consistency: 'Strategy Consistency',
};

const DIMENSION_ORDER = [
  'regime_fit',
  'entry_timing',
  'exit_logic',
  'risk_positioning',
  'behavioral',
  'strategy_consistency',
];

interface EvaluationDisplayProps {
  evaluation: EvaluationResponse;
}

export default function EvaluationDisplay({ evaluation }: EvaluationDisplayProps) {
  const [activeTab, setActiveTab] = useState<string | null>(null);

  // Group items by evaluator
  const itemsByDimension: Record<string, EvaluationItemResponse[]> = {};
  for (const item of evaluation.all_items) {
    if (!itemsByDimension[item.evaluator]) {
      itemsByDimension[item.evaluator] = [];
    }
    itemsByDimension[item.evaluator].push(item);
  }

  // Find worst severity per dimension
  const worstSeverity = (items: EvaluationItemResponse[]): Severity => {
    const order: Severity[] = ['blocker', 'critical', 'warning', 'info'];
    for (const sev of order) {
      if (items.some((i) => i.severity === sev)) return sev;
    }
    return 'info';
  };

  return (
    <div>
      {/* Summary bar */}
      <SeveritySummaryBar counts={evaluation.counts} hasBlockers={evaluation.has_blockers} />

      {/* Evaluation summary text */}
      <div className="mb-6 rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
        <p className="text-sm text-[var(--text-primary)]">{evaluation.summary}</p>
        <div className="mt-2 text-xs text-[var(--text-secondary)]">
          Score: {evaluation.score}/100 &middot; Evaluated {new Date(evaluation.evaluated_at).toLocaleString()}
        </div>
      </div>

      {/* Dimension tabs */}
      <div className="mb-4 flex flex-wrap gap-2">
        {DIMENSION_ORDER.filter((d) => evaluation.evaluators_run.includes(d)).map((dim) => {
          const items = itemsByDimension[dim] ?? [];
          const worst = items.length > 0 ? worstSeverity(items) : 'info';
          const isActive = activeTab === dim;

          return (
            <button
              key={dim}
              onClick={() => setActiveTab(isActive ? null : dim)}
              className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-sm transition-colors ${
                isActive
                  ? 'border-[var(--accent-blue)] bg-[var(--accent-blue)]/10 text-[var(--text-primary)]'
                  : 'border-[var(--border-color)] text-[var(--text-secondary)] hover:border-[var(--text-secondary)] hover:text-[var(--text-primary)]'
              }`}
            >
              <DimensionStatusDot severity={worst} />
              {DIMENSION_LABELS[dim] ?? dim}
              {items.length > 0 && worst !== 'info' && (
                <span className="text-xs opacity-60">({items.length})</span>
              )}
            </button>
          );
        })}
      </div>

      {/* Expanded dimension content */}
      {activeTab && (
        <DimensionPanel
          dimension={activeTab}
          items={itemsByDimension[activeTab] ?? []}
        />
      )}

      {/* If no tab selected, show all top issues */}
      {!activeTab && evaluation.top_issues.length > 0 && (
        <div>
          <h3 className="mb-3 text-sm font-medium text-[var(--text-secondary)]">Top Issues</h3>
          <div className="space-y-3">
            {evaluation.top_issues.map((item, idx) => (
              <EvaluationItemCard key={`${item.code}-${idx}`} item={item} />
            ))}
          </div>
        </div>
      )}

      {/* No issues */}
      {!activeTab && evaluation.top_issues.length === 0 && (
        <div className="rounded-lg border border-[var(--accent-green)]/30 bg-[var(--accent-green)]/5 p-4 text-sm text-[var(--accent-green)]">
          No issues found. All evaluation dimensions passed.
        </div>
      )}
    </div>
  );
}

// --- Sub-components ---

function SeveritySummaryBar({ counts, hasBlockers }: { counts: Record<string, number>; hasBlockers: boolean }) {
  return (
    <div className="mb-4 flex flex-wrap items-center gap-3">
      {hasBlockers && (
        <div className="flex items-center gap-1.5 rounded-md bg-[var(--accent-red)]/15 px-3 py-1.5 text-xs font-medium text-[var(--accent-red)]">
          {'\u26D4'} {counts.blocker ?? 0} blocker{(counts.blocker ?? 0) !== 1 ? 's' : ''}
        </div>
      )}
      {(counts.critical ?? 0) > 0 && (
        <div className="flex items-center gap-1.5 text-xs text-[var(--accent-red)]">
          {'\u2716'} {counts.critical} critical
        </div>
      )}
      {(counts.warning ?? 0) > 0 && (
        <div className="flex items-center gap-1.5 text-xs text-[var(--accent-yellow)]">
          {'\u26A0'} {counts.warning} warning{counts.warning !== 1 ? 's' : ''}
        </div>
      )}
      {(counts.info ?? 0) > 0 && (
        <div className="flex items-center gap-1.5 text-xs text-[var(--accent-blue)]">
          {'\u2139'} {counts.info} info
        </div>
      )}
    </div>
  );
}

function DimensionStatusDot({ severity }: { severity: Severity }) {
  const colors: Record<Severity, string> = {
    info: 'bg-[var(--accent-blue)]',
    warning: 'bg-[var(--accent-yellow)]',
    critical: 'bg-[var(--accent-red)]',
    blocker: 'bg-[var(--accent-red)]',
  };

  return (
    <span className={`inline-block h-2 w-2 rounded-full ${colors[severity]}`} />
  );
}

function DimensionPanel({ dimension, items }: { dimension: string; items: EvaluationItemResponse[] }) {
  if (items.length === 0) {
    return (
      <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
        <h3 className="mb-2 text-sm font-medium">{DIMENSION_LABELS[dimension] ?? dimension}</h3>
        <p className="text-sm text-[var(--text-secondary)]">No findings for this dimension. All clear.</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-medium text-[var(--text-secondary)]">
        {DIMENSION_LABELS[dimension] ?? dimension}
      </h3>
      {items.map((item, idx) => (
        <EvaluationItemCard key={`${item.code}-${idx}`} item={item} />
      ))}
    </div>
  );
}

function EvaluationItemCard({ item }: { item: EvaluationItemResponse }) {
  return (
    <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
      {/* Header */}
      <div className="mb-2 flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <SeverityIcon severity={item.severity} />
          <span className="text-sm font-medium">{item.title}</span>
        </div>
        <SeverityBadge severity={item.severity} />
      </div>

      {/* Message */}
      <p className="mb-3 text-sm text-[var(--text-secondary)]">{item.message}</p>

      {/* Evidence */}
      {item.evidence.length > 0 && (
        <div className="rounded-md border border-[var(--border-color)] bg-[var(--bg-primary)] p-3">
          <div className="mb-1.5 text-xs font-medium text-[var(--text-secondary)]">Evidence</div>
          <div className="space-y-1.5">
            {item.evidence.map((ev, i) => (
              <div key={i} className="flex items-center gap-2 text-xs">
                <span className="font-mono text-[var(--text-secondary)]">{ev.metric_name}</span>
                <span className="text-[var(--text-primary)]">
                  {ev.comparison && ev.threshold != null ? (
                    <>
                      <span className="font-mono font-medium">{formatValue(ev.value, ev.unit)}</span>
                      <span className="text-[var(--text-secondary)]">
                        {' '}{ev.comparison}{' '}{formatValue(ev.threshold, ev.unit)}
                      </span>
                    </>
                  ) : (
                    <span className="font-mono font-medium">{formatValue(ev.value, ev.unit)}</span>
                  )}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Evaluator + code tag */}
      <div className="mt-2 flex items-center gap-2 text-[10px] text-[var(--text-secondary)]">
        <span>{DIMENSION_LABELS[item.evaluator] ?? item.evaluator}</span>
        <span>&middot;</span>
        <span className="font-mono">{item.code}</span>
      </div>
    </div>
  );
}

function formatValue(value: number, unit: string | null): string {
  if (unit === '%') return `${(value * 100).toFixed(1)}%`;
  if (unit === 'minutes') return `${value} min`;
  if (unit === 'USD') return `$${value.toFixed(2)}`;
  if (unit === 'percentile') return `${value}th pctile`;
  return String(value);
}
