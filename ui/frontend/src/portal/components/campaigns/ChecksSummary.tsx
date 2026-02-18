import { useMemo } from 'react';
import type { CampaignCheck, CheckSeverity } from '../../types';

interface ChecksSummaryProps {
  checks: CampaignCheck[];
  legLabel?: string;
  showSummary?: boolean;
}

interface CheckTypeGroupData {
  checkType: string;
  checks: CampaignCheck[];
  highestSeverity: CheckSeverity;
}

const SEVERITY_ORDER: Record<CheckSeverity, number> = {
  critical: 0,
  warn: 1,
  info: 2,
};

const SEVERITY_COLORS: Record<CheckSeverity, string> = {
  critical: 'text-[var(--accent-red)]',
  warn: 'text-[var(--accent-yellow)]',
  info: 'text-[var(--accent-blue)]',
};

const SEVERITY_DOT: Record<CheckSeverity, string> = {
  critical: 'bg-[var(--accent-red)]',
  warn: 'bg-[var(--accent-yellow)]',
  info: 'bg-[var(--accent-blue)]',
};

function formatCheckType(checkType: string): string {
  return checkType
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}

function groupChecksByType(checks: CampaignCheck[]): CheckTypeGroupData[] {
  const grouped = new Map<string, CampaignCheck[]>();
  for (const check of checks) {
    const list = grouped.get(check.checkType);
    if (list) list.push(check);
    else grouped.set(check.checkType, [check]);
  }

  const groups: CheckTypeGroupData[] = [];
  for (const [checkType, groupChecks] of grouped) {
    let highest: CheckSeverity = 'info';
    for (const c of groupChecks) {
      if (SEVERITY_ORDER[c.severity] < SEVERITY_ORDER[highest]) highest = c.severity;
    }
    // Sort: failed first, then by severity
    groupChecks.sort((a, b) => {
      if (a.passed !== b.passed) return a.passed ? 1 : -1;
      return SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity];
    });
    groups.push({ checkType, checks: groupChecks, highestSeverity: highest });
  }

  groups.sort((a, b) => {
    const d = SEVERITY_ORDER[a.highestSeverity] - SEVERITY_ORDER[b.highestSeverity];
    return d !== 0 ? d : a.checkType.localeCompare(b.checkType);
  });

  return groups;
}

export function ChecksSummary({ checks, legLabel, showSummary = true }: ChecksSummaryProps) {
  const passed = checks.filter((c) => c.passed).length;
  const failed = checks.filter((c) => !c.passed).length;
  const groups = useMemo(() => groupChecksByType(checks), [checks]);

  return (
    <div>
      {legLabel && (
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--text-secondary)]">
          {legLabel}
        </h3>
      )}
      {showSummary && (
        <div className="mb-3 flex gap-3 text-xs">
          <span className="text-[var(--accent-green)]">{passed} passed</span>
          {failed > 0 && <span className="text-[var(--accent-red)]">{failed} failed</span>}
        </div>
      )}

      <div className="space-y-2">
        {groups.map((group) => (
          <div key={group.checkType} className="rounded-md border border-[var(--border-color)] overflow-hidden">
            {/* Group header */}
            <div className="flex items-center gap-2 bg-[var(--bg-tertiary)]/40 px-3 py-1.5">
              <span className={`h-1.5 w-1.5 rounded-full ${SEVERITY_DOT[group.highestSeverity]}`} />
              <span className="text-xs font-semibold text-[var(--text-primary)]">
                {formatCheckType(group.checkType)}
              </span>
              <span className="text-[10px] text-[var(--text-secondary)]">
                ({group.checks.length})
              </span>
            </div>
            {/* Compact table of nudge texts */}
            <table className="w-full text-xs">
              <tbody>
                {group.checks.map((check) => (
                  <tr key={check.checkId} className="border-t border-[var(--border-color)]">
                    <td className="w-5 px-2 py-1 text-center">
                      <span className={`inline-block h-1.5 w-1.5 rounded-full ${check.passed ? 'bg-[var(--accent-green)]' : 'bg-[var(--accent-red)]'}`} />
                    </td>
                    <td className={`w-14 px-1 py-1 text-[10px] font-medium ${SEVERITY_COLORS[check.severity]}`}>
                      {check.severity}
                    </td>
                    <td className="px-2 py-1 text-[var(--text-secondary)]">
                      {check.nudgeText || check.code}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}
      </div>
    </div>
  );
}
