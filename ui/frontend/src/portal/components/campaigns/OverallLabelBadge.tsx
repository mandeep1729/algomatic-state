import type { OverallLabel } from '../../types';

const LABEL_STYLES: Record<OverallLabel, string> = {
  aligned: 'bg-[var(--accent-green)]/10 text-[var(--accent-green)]',
  mixed: 'bg-[var(--accent-yellow)]/10 text-[var(--accent-yellow)]',
  fragile: 'bg-[var(--accent-yellow)]/20 text-[var(--accent-yellow)]',
  deviates: 'bg-[var(--accent-red)]/10 text-[var(--accent-red)]',
};

const LABEL_DISPLAY: Record<OverallLabel, string> = {
  aligned: 'Aligned',
  mixed: 'Mixed',
  fragile: 'Fragile',
  deviates: 'Deviates',
};

export function OverallLabelBadge({ label }: { label: OverallLabel }) {
  return (
    <span
      className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${LABEL_STYLES[label]}`}
    >
      {LABEL_DISPLAY[label]}
    </span>
  );
}
