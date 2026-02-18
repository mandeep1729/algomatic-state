/**
 * DriverCard — displays a single driver in the WHY panel.
 */

import type { Driver } from '../../utils/investigateDrivers';
import { useInvestigate } from '../../context/InvestigateContext';

const DIMENSION_LABELS: Record<string, string> = {
  symbol: 'Ticker',
  strategy: 'Strategy',
  flag: 'Flag',
  direction: 'Direction',
};

export function DriverCard({ driver, variant }: { driver: Driver; variant: 'negative' | 'positive' }) {
  const { addFilter } = useInvestigate();

  const borderColor = variant === 'negative'
    ? 'border-l-[var(--accent-red)]'
    : 'border-l-[var(--accent-green)]';

  const pnlColor = variant === 'negative'
    ? 'text-[var(--accent-red)]'
    : 'text-[var(--accent-green)]';

  const confidenceColor =
    driver.confidence === 'low' ? 'text-[var(--accent-red)]'
      : driver.confidence === 'medium' ? 'text-[var(--accent-yellow)]'
        : 'text-[var(--accent-green)]';

  function handleClick() {
    const field = driver.dimension === 'symbol' ? 'symbol'
      : driver.dimension === 'strategy' ? 'strategy'
        : driver.dimension === 'flag' ? 'flag'
          : 'direction';
    addFilter(field, 'eq', driver.key, `${DIMENSION_LABELS[driver.dimension]}: ${driver.key}`, 'chart-click');
  }

  return (
    <button
      onClick={handleClick}
      className={`w-full rounded-md border border-[var(--border-color)] border-l-2 ${borderColor} bg-[var(--bg-secondary)] p-2.5 text-left transition-colors hover:bg-[var(--bg-tertiary)]/50`}
    >
      <div className="flex items-center justify-between mb-1">
        <span className="text-[10px] uppercase tracking-wider text-[var(--text-secondary)]">
          {DIMENSION_LABELS[driver.dimension]}
        </span>
        <span className={`text-[10px] font-medium ${confidenceColor}`}>
          {driver.confidence}
        </span>
      </div>
      <div className="text-xs font-medium text-[var(--text-primary)] mb-1">
        {driver.key}
      </div>
      <div className={`text-sm font-semibold font-mono ${pnlColor}`}>
        {driver.totalPnl >= 0 ? '+' : ''}${driver.totalPnl.toFixed(0)}
      </div>
      <div className="mt-1 text-[10px] text-[var(--text-secondary)] leading-relaxed">
        {driver.explanation}
      </div>
    </button>
  );
}
