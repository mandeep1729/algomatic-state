import type { CampaignLeg } from '../../types';

interface TimelineProps {
  legs: CampaignLeg[];
  activeIndex: number;
  onSelect: (index: number) => void;
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

export function Timeline({ legs, activeIndex, onSelect }: TimelineProps) {
  return (
    <div className="flex items-start overflow-x-auto py-4">
      {legs.map((leg, idx) => {
        const isActive = idx === activeIndex;

        return (
          <div key={leg.legId} className="flex items-start">
            {/* Leg node */}
            <div className="flex flex-col items-center">
              <button
                type="button"
                onClick={() => onSelect(idx)}
                title={`${leg.legType.toUpperCase()} ${leg.side.toUpperCase()} ${leg.quantity}`}
                className={`flex h-8 w-8 items-center justify-center rounded-full border-2 transition-colors ${
                  isActive
                    ? 'border-[var(--accent-blue)] bg-[var(--accent-blue)] text-white'
                    : 'border-[var(--border-color)] bg-[var(--bg-secondary)] text-[var(--text-secondary)] hover:border-[var(--accent-blue)] hover:text-[var(--text-primary)]'
                }`}
              >
                <span className="text-[10px] font-bold">{idx + 1}</span>
              </button>

              {/* Labels below dot */}
              <div className="mt-2 flex flex-col items-center">
                <span
                  className={`text-xs font-medium ${
                    isActive ? 'text-[var(--accent-blue)]' : 'text-[var(--text-primary)]'
                  }`}
                >
                  {leg.legType.toUpperCase()}
                </span>
                <span className="text-[10px] text-[var(--text-secondary)]">
                  {leg.side === 'buy' ? '+' : '-'}
                  {leg.quantity} @ {leg.avgPrice.toFixed(2)}
                </span>
                <span className="text-[10px] text-[var(--text-secondary)]">
                  {formatDate(leg.startedAt)}
                </span>
              </div>
            </div>

            {/* Connecting line */}
            {idx < legs.length - 1 && (
              <div className="mt-3.5 flex items-center px-1">
                <div className="h-0.5 w-12 bg-[var(--border-color)]" />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
