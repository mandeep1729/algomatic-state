import { useMemo, useState } from 'react';
import { Search, Copy } from 'lucide-react';
import type { AgentStrategy } from '../../types';

const CATEGORY_LABELS: Record<string, string> = {
  trend: 'Trend Following',
  mean_reversion: 'Mean Reversion',
  breakout: 'Breakout',
  volume_flow: 'Volume Flow',
  pattern: 'Pattern',
  regime: 'Regime',
  custom: 'Custom',
};

interface StrategyPickerProps {
  strategies: AgentStrategy[];
  selectedId: number | null;
  onSelect: (id: number) => void;
  onClone?: (strategyId: number) => void;
}

export function StrategyPicker({ strategies, selectedId, onSelect, onClone }: StrategyPickerProps) {
  const [search, setSearch] = useState('');

  const filtered = useMemo(() => {
    const q = search.toLowerCase().trim();
    if (!q) return strategies;
    return strategies.filter(
      (s) =>
        s.name.toLowerCase().includes(q) ||
        s.display_name.toLowerCase().includes(q) ||
        (s.description ?? '').toLowerCase().includes(q),
    );
  }, [strategies, search]);

  const grouped = useMemo(() => {
    const groups: Record<string, AgentStrategy[]> = {};
    for (const s of filtered) {
      const cat = s.category || 'custom';
      if (!groups[cat]) groups[cat] = [];
      groups[cat].push(s);
    }
    return groups;
  }, [filtered]);

  const categoryOrder = ['trend', 'mean_reversion', 'breakout', 'volume_flow', 'pattern', 'regime', 'custom'];
  const sortedCategories = Object.keys(grouped).sort(
    (a, b) => (categoryOrder.indexOf(a) === -1 ? 99 : categoryOrder.indexOf(a)) -
              (categoryOrder.indexOf(b) === -1 ? 99 : categoryOrder.indexOf(b)),
  );

  return (
    <div className="space-y-3">
      {/* Search */}
      <div className="relative">
        <Search size={13} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--text-secondary)]" />
        <input
          type="text"
          placeholder="Search strategies..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="form-input h-8 w-full pl-8 pr-3 text-xs"
        />
      </div>

      {/* Strategy list */}
      <div className="max-h-[320px] space-y-4 overflow-y-auto pr-1 scrollbar-thin scrollbar-track-transparent scrollbar-thumb-[var(--border-color)]">
        {sortedCategories.length === 0 && (
          <p className="py-4 text-center text-xs text-[var(--text-secondary)]">No strategies found.</p>
        )}
        {sortedCategories.map((cat) => (
          <div key={cat}>
            <h4 className="mb-1.5 text-[10px] font-medium uppercase tracking-wider text-[var(--text-secondary)]">
              {CATEGORY_LABELS[cat] ?? cat}
            </h4>
            <div className="space-y-1.5">
              {grouped[cat].map((s) => {
                const isSelected = s.id === selectedId;
                return (
                  <button
                    key={s.id}
                    type="button"
                    onClick={() => onSelect(s.id)}
                    className={`flex w-full items-start gap-3 rounded-lg border p-3 text-left transition-colors ${
                      isSelected
                        ? 'border-[var(--accent-blue)] bg-[var(--accent-blue)]/5'
                        : 'border-[var(--border-color)] hover:border-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)]/30'
                    }`}
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-[var(--text-primary)]">{s.display_name}</span>
                        <span className="inline-block rounded px-1.5 py-0.5 text-[10px] font-medium bg-[var(--bg-tertiary)] text-[var(--text-secondary)]">
                          {s.direction.replace('_', ' ')}
                        </span>
                      </div>
                      {s.description && (
                        <p className="mt-0.5 text-xs text-[var(--text-secondary)] line-clamp-2">{s.description}</p>
                      )}
                    </div>
                    {s.is_predefined && onClone && (
                      <button
                        type="button"
                        onClick={(e) => { e.stopPropagation(); onClone(s.id); }}
                        className="flex-shrink-0 rounded p-1 text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-primary)] transition-colors"
                        title="Clone strategy"
                      >
                        <Copy size={14} />
                      </button>
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
