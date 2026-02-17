import type { StrategyDefinition } from '../../types';
import { mergeStrategies } from '../../utils/defaultStrategies';

interface StrategyChipsProps {
  value: string[];
  onChange: (v: string[]) => void;
  strategies: StrategyDefinition[];
  loading?: boolean;
}

export function StrategyChips({ value, onChange, strategies, loading }: StrategyChipsProps) {
  const toggle = (strategyId: string) => {
    const set = new Set(value);
    if (set.has(strategyId)) {
      set.delete(strategyId);
    } else {
      set.add(strategyId);
    }
    onChange(Array.from(set));
  };

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-xs text-[var(--text-secondary)]">
        Loading strategies...
      </div>
    );
  }

  // Merge user-defined strategies with default family strategies
  const mergedStrategies = mergeStrategies(
    strategies.filter((s) => s.is_active).map((s) => ({ id: s.id, name: s.name })),
    true, // Include default strategies
  );

  if (mergedStrategies.length === 0) {
    return (
      <div className="text-xs text-[var(--text-secondary)]">
        No strategies available.{' '}
        <a href="/app/settings/strategies" className="text-[var(--accent-blue)] hover:underline">
          Create one
        </a>
      </div>
    );
  }

  return (
    <div className="flex flex-wrap gap-2">
      {mergedStrategies.map((strategy) => {
        const isActive = value.includes(strategy.id);
        return (
          <button
            key={strategy.id}
            type="button"
            onClick={() => toggle(strategy.id)}
            title={strategy.name}
            className={`rounded-full border px-3 py-1 text-xs transition-colors ${
              isActive
                ? 'border-[var(--accent-blue)] bg-[var(--accent-blue)]/10 text-[var(--accent-blue)]'
                : 'border-[var(--border-color)] text-[var(--text-secondary)] hover:border-[var(--text-secondary)] hover:text-[var(--text-primary)]'
            }`}
          >
            {strategy.name}
          </button>
        );
      })}
    </div>
  );
}
