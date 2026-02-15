import { useState } from 'react';
import type { CampaignCheck, CheckSeverity } from '../../types';

interface ChecksSummaryProps {
  checks: CampaignCheck[];
  /** Optional label displayed above the summary counts (e.g. "L1: open") */
  legLabel?: string;
  /** Optional flag to show/hide summary counts (default: true) */
  showSummary?: boolean;
}

const SEVERITY_ORDER: Record<CheckSeverity, number> = {
  critical: 0,
  warn: 1,
  info: 2,
};

const SEVERITY_STYLES: Record<CheckSeverity, { badge: string; dot: string }> = {
  info: {
    badge: 'bg-[var(--accent-blue)]/10 text-[var(--accent-blue)]',
    dot: 'bg-[var(--accent-blue)]',
  },
  warn: {
    badge: 'bg-[var(--accent-yellow)]/10 text-[var(--accent-yellow)]',
    dot: 'bg-[var(--accent-yellow)]',
  },
  critical: {
    badge: 'bg-[var(--accent-red)]/10 text-[var(--accent-red)]',
    dot: 'bg-[var(--accent-red)]',
  },
};

/** Severities that count as "critical" for badge/blocker purposes. */
const CRITICAL_SEVERITIES: ReadonlySet<CheckSeverity> = new Set(['block', 'danger', 'critical']);

function sortChecks(checks: CampaignCheck[]): CampaignCheck[] {
  return [...checks].sort((a, b) => {
    // Failed checks first
    if (a.passed !== b.passed) return a.passed ? 1 : -1;
    // Then by severity (critical > warn > info)
    return SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity];
  });
}

function CheckCard({ check }: { check: CampaignCheck }) {
  const [isOpen, setIsOpen] = useState(false);
  const style = SEVERITY_STYLES[check.severity] ?? SEVERITY_STYLES.info;

  return (
    <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)]">
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        className="flex w-full items-start justify-between gap-3 p-4 text-left"
      >
        <div className="flex items-start gap-3 min-w-0">
          {/* Pass/fail dot */}
          <span className={`mt-1 h-2.5 w-2.5 shrink-0 rounded-full ${check.passed ? 'bg-[var(--accent-green)]' : 'bg-[var(--accent-red)]'}`} />

          <div className="min-w-0">
            <div className="text-sm font-medium text-[var(--text-primary)]">
              {check.code}
            </div>
            {check.nudgeText && (
              <div className="mt-0.5 text-xs text-[var(--text-secondary)] line-clamp-2">
                {check.nudgeText}
              </div>
            )}
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          <span className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${style.badge}`}>
            {check.severity}
          </span>
          <svg
            className={`h-4 w-4 text-[var(--text-secondary)] transition-transform ${isOpen ? 'rotate-180' : ''}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </button>

      {isOpen && (
        <div className="border-t border-[var(--border-color)] px-4 pb-4 pt-3">
          <div className="grid grid-cols-2 gap-2 text-xs text-[var(--text-secondary)]">
            <span>Type: {check.checkType}</span>
            <span>Phase: {check.checkPhase}</span>
            <span>Checked: {new Date(check.checkedAt).toLocaleString('en-US', { timeZone: 'America/New_York' })}</span>
            {check.acknowledged != null && (
              <span>Acknowledged: {check.acknowledged ? 'Yes' : 'No'}</span>
            )}
            {check.traderAction && (
              <span>Action: {check.traderAction}</span>
            )}
          </div>

          {check.details && Object.keys(check.details).length > 0 && (
            <details className="mt-3">
              <summary className="cursor-pointer text-xs font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)]">
                Details
              </summary>
              <pre className="mt-2 overflow-x-auto rounded-md border border-[var(--border-color)] bg-[var(--bg-primary)] p-3 text-xs text-[var(--text-secondary)]">
                {JSON.stringify(check.details, null, 2)}
              </pre>
            </details>
          )}
        </div>
      )}
    </div>
  );
}

export function ChecksSummary({ checks, legLabel, showSummary = true }: ChecksSummaryProps) {
  const passed = checks.filter((c) => c.passed).length;
  const failed = checks.filter((c) => !c.passed).length;
  const warnings = checks.filter((c) => c.severity === 'warn' && !c.passed).length;
  const blockers = checks.filter((c) => c.severity === 'critical' && !c.passed).length;

  const sorted = sortChecks(checks);

  return (
    <div>
      {legLabel && (
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--text-secondary)]">
          {legLabel}
        </h3>
      )}
      {/* Summary counts */}
      {showSummary && (
        <div className="mb-4 flex flex-wrap gap-3 text-xs">
          <span className="text-[var(--accent-green)]">
            {passed} passed
          </span>
          {warnings > 0 && (
            <span className="text-[var(--accent-yellow)]">
              {warnings} warning{warnings !== 1 ? 's' : ''}
            </span>
          )}
          {blockers > 0 && (
            <span className="text-[var(--accent-red)]">
              {blockers} blocker{blockers !== 1 ? 's' : ''}
            </span>
          )}
          {failed > 0 && failed !== warnings + blockers && (
            <span className="text-[var(--accent-red)]">
              {failed} failed
            </span>
          )}
        </div>
      )}

      {/* Check cards */}
      <div className="grid gap-3">
        {sorted.map((check) => (
          <CheckCard key={check.checkId} check={check} />
        ))}
      </div>
    </div>
  );
}
