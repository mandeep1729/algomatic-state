/**
 * FilterBar — horizontal row of active filter chips with clear-all and compare toggle.
 */

import { X } from 'lucide-react';
import { useInvestigate } from '../../context/InvestigateContext';
import { CompareToggle } from './CompareToggle';

export function FilterBar() {
  const { filters, removeFilter, clearFilters } = useInvestigate();

  if (filters.length === 0) {
    return (
      <div className="flex items-center justify-between px-6 py-2">
        <span className="text-xs text-[var(--text-secondary)]">
          Click any chart element to add filters
        </span>
        <CompareToggle />
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2 px-6 py-2 flex-wrap">
      {filters.map((chip) => (
        <span
          key={chip.id}
          className="inline-flex items-center gap-1.5 rounded-full bg-[var(--accent-blue)]/10 px-3 py-1 text-xs font-medium text-[var(--accent-blue)]"
        >
          {chip.label}
          <button
            onClick={() => removeFilter(chip.id)}
            className="rounded-full p-0.5 hover:bg-[var(--accent-blue)]/20"
          >
            <X size={12} />
          </button>
        </span>
      ))}
      <button
        onClick={clearFilters}
        className="text-xs text-[var(--text-secondary)] hover:text-[var(--accent-red)]"
      >
        Clear All
      </button>
      <div className="ml-auto">
        <CompareToggle />
      </div>
    </div>
  );
}
