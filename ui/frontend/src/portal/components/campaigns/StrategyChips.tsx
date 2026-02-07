const STRATEGY_OPTIONS = [
  'breakout',
  'pullback',
  'momentum',
  'mean_reversion',
  'range_fade',
  'news',
  'other',
] as const;

interface StrategyChipsProps {
  value: string[];
  onChange: (v: string[]) => void;
}

export function StrategyChips({ value, onChange }: StrategyChipsProps) {
  const toggle = (tag: string) => {
    const set = new Set(value);
    if (set.has(tag)) {
      set.delete(tag);
    } else {
      set.add(tag);
    }
    onChange(Array.from(set));
  };

  return (
    <div className="flex flex-wrap gap-2">
      {STRATEGY_OPTIONS.map((option) => {
        const isActive = value.includes(option);
        return (
          <button
            key={option}
            type="button"
            onClick={() => toggle(option)}
            className={`rounded-full border px-3 py-1 text-xs transition-colors ${
              isActive
                ? 'border-[var(--accent-blue)] bg-[var(--accent-blue)]/10 text-[var(--accent-blue)]'
                : 'border-[var(--border-color)] text-[var(--text-secondary)] hover:border-[var(--text-secondary)] hover:text-[var(--text-primary)]'
            }`}
          >
            {option.replace(/_/g, ' ')}
          </button>
        );
      })}
    </div>
  );
}
