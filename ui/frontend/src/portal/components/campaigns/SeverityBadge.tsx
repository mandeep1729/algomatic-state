import type { CampaignSeverity } from '../../types';

const SEVERITY_STYLES: Record<CampaignSeverity, string> = {
  info: 'bg-[var(--accent-blue)]/10 text-[var(--accent-blue)]',
  low: 'bg-[var(--accent-green)]/10 text-[var(--accent-green)]',
  medium: 'bg-[var(--accent-yellow)]/10 text-[var(--accent-yellow)]',
  high: 'bg-[var(--accent-red)]/10 text-[var(--accent-red)]',
};

export function SeverityBadge({ severity }: { severity: CampaignSeverity }) {
  return (
    <span
      className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${SEVERITY_STYLES[severity]}`}
    >
      {severity}
    </span>
  );
}
