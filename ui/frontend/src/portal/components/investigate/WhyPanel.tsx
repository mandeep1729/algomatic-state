/**
 * WhyPanel — right sidebar showing top negative/positive drivers.
 * Always visible, updates when filters change.
 */

import { AlertTriangle, TrendingUp, Info } from 'lucide-react';
import { useInvestigate } from '../../context/InvestigateContext';
import { DriverCard } from './DriverCard';

export function WhyPanel() {
  const { drivers, subsetMetrics } = useInvestigate();
  const hasDrivers = drivers.negative.length > 0 || drivers.positive.length > 0;

  return (
    <div className="flex h-full w-[280px] flex-shrink-0 flex-col border-l border-[var(--border-color)] bg-[var(--bg-primary)]">
      {/* Header */}
      <div className="border-b border-[var(--border-color)] px-4 py-3">
        <h3 className="text-sm font-semibold text-[var(--text-primary)]">WHY Panel</h3>
        <p className="mt-0.5 text-[10px] text-[var(--text-secondary)]">
          What's hurting and helping your trading
        </p>
      </div>

      <div className="flex-1 overflow-y-auto px-3 py-3 space-y-4">
        {!hasDrivers ? (
          <div className="flex flex-col items-center justify-center py-8 text-center">
            <Info size={24} className="mb-2 text-[var(--text-secondary)]" />
            <p className="text-xs text-[var(--text-secondary)]">
              No closed campaigns to analyze yet.
              Drivers will appear once you have trade data.
            </p>
          </div>
        ) : (
          <>
            {/* Hurting section */}
            {drivers.negative.length > 0 && (
              <div>
                <div className="mb-2 flex items-center gap-1.5">
                  <AlertTriangle size={12} className="text-[var(--accent-red)]" />
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--accent-red)]">
                    Hurting
                  </span>
                </div>
                <div className="space-y-2">
                  {drivers.negative.map((d) => (
                    <DriverCard key={`${d.dimension}-${d.key}`} driver={d} variant="negative" />
                  ))}
                </div>
              </div>
            )}

            {/* Helping section */}
            {drivers.positive.length > 0 && (
              <div>
                <div className="mb-2 flex items-center gap-1.5">
                  <TrendingUp size={12} className="text-[var(--accent-green)]" />
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--accent-green)]">
                    Helping
                  </span>
                </div>
                <div className="space-y-2">
                  {drivers.positive.map((d) => (
                    <DriverCard key={`${d.dimension}-${d.key}`} driver={d} variant="positive" />
                  ))}
                </div>
              </div>
            )}

            {/* Confidence footer */}
            <div className="rounded-md bg-[var(--bg-tertiary)]/50 p-2.5">
              <div className="flex items-center gap-1.5 mb-1">
                <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
                  Sample Size
                </span>
              </div>
              <div className={`text-xs font-medium ${
                subsetMetrics.confidence === 'low' ? 'text-[var(--accent-red)]'
                  : subsetMetrics.confidence === 'medium' ? 'text-[var(--accent-yellow)]'
                    : 'text-[var(--accent-green)]'
              }`}>
                {subsetMetrics.tradeCount} closed trades — {subsetMetrics.confidence} confidence
              </div>
              {subsetMetrics.confidence === 'low' && (
                <p className="mt-1 text-[10px] text-[var(--text-secondary)]">
                  Results may not be statistically meaningful with fewer than 30 trades.
                </p>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
