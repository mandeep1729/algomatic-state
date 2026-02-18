/**
 * CompareToggle — All vs Subset toggle.
 */

import { useInvestigate } from '../../context/InvestigateContext';

export function CompareToggle() {
  const { compareEnabled, toggleCompare, filters } = useInvestigate();

  if (filters.length === 0) return null;

  return (
    <button
      onClick={toggleCompare}
      className={`flex items-center gap-1.5 rounded-md px-3 py-1 text-xs font-medium transition-colors ${
        compareEnabled
          ? 'bg-[var(--accent-purple)]/15 text-[var(--accent-purple)]'
          : 'bg-[var(--bg-tertiary)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
      }`}
    >
      <span className={`inline-block h-2 w-2 rounded-full ${compareEnabled ? 'bg-[var(--accent-purple)]' : 'bg-[var(--text-secondary)]'}`} />
      {compareEnabled ? 'Comparing: All vs Subset' : 'Compare Mode'}
    </button>
  );
}
