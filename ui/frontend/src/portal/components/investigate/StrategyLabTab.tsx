/**
 * StrategyLabTab — PnL by strategy, strategy comparison, return distribution.
 */

import { useState, useMemo } from 'react';
import { useInvestigate } from '../../context/InvestigateContext';
import { Section } from '../ui/Section';
import { PnlByGroupChart, type GroupedPnl } from '../charts/PnlByGroupChart';
import { ReturnDistributionChart } from '../charts/ReturnDistributionChart';
import { ChartHelp } from './ChartHelp';
import { computeExpectancy } from '../../utils/dashboardMetrics';
import { confidenceFromCount } from '../../utils/investigateMetrics';

interface StrategyStats {
  name: string;
  totalPnl: number;
  tradeCount: number;
  winRate: number;
  avgPnl: number;
  expectancy: number | null;
  returns: number[];
}

export function StrategyLabTab() {
  const { subset, addFilter } = useInvestigate();
  const [selectedStrategies, setSelectedStrategies] = useState<string[]>([]);

  // Compute per-strategy stats
  const strategyStats = useMemo((): StrategyStats[] => {
    const map = new Map<string, { returns: number[] }>();

    for (const c of subset) {
      if (c.status !== 'closed' || c.pnlRealized == null) continue;
      const keys = c.strategies.length > 0 ? c.strategies : ['(none)'];
      for (const key of keys) {
        const acc = map.get(key) ?? { returns: [] };
        acc.returns.push(c.pnlRealized);
        map.set(key, acc);
      }
    }

    return Array.from(map.entries()).map(([name, { returns }]) => {
      const totalPnl = returns.reduce((a, b) => a + b, 0);
      const wins = returns.filter((r) => r > 0).length;
      return {
        name,
        totalPnl,
        tradeCount: returns.length,
        winRate: returns.length > 0 ? wins / returns.length : 0,
        avgPnl: returns.length > 0 ? totalPnl / returns.length : 0,
        expectancy: computeExpectancy(returns),
        returns,
      };
    });
  }, [subset]);

  const groupedData = useMemo((): GroupedPnl[] =>
    strategyStats.map((s) => ({
      key: s.name,
      totalPnl: s.totalPnl,
      tradeCount: s.tradeCount,
    })),
    [strategyStats],
  );

  // Toggle strategy selection for comparison
  function toggleStrategy(name: string) {
    setSelectedStrategies((prev) => {
      if (prev.includes(name)) return prev.filter((s) => s !== name);
      if (prev.length >= 2) return [prev[1], name]; // Keep max 2
      return [...prev, name];
    });
  }

  function handleBarClick(key: string) {
    addFilter('strategy', 'eq', key, `Strategy: ${key}`, 'chart-click');
  }

  const comparedStats = strategyStats.filter((s) => selectedStrategies.includes(s.name));

  return (
    <div className="space-y-6 pt-4">
      {/* PnL by Strategy */}
      <Section title="P&L by Strategy">
        <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-3">
          {groupedData.length > 0 ? (
            <PnlByGroupChart data={groupedData} height={260} onBarClick={handleBarClick} />
          ) : (
            <div className="flex h-[260px] items-center justify-center text-sm text-[var(--text-secondary)]">
              No strategy data available. Tag your campaigns with strategies to see this chart.
            </div>
          )}
        </div>
        <ChartHelp
          what="Total P&L contribution of each strategy across your filtered campaigns."
          how="Compare strategies side-by-side. Losing strategies may need rule refinement or should be paused."
          click="Click a bar to filter by that strategy. Select 2 strategies below for detailed comparison."
        />
      </Section>

      {/* Strategy Selector */}
      {strategyStats.length > 0 && (
        <Section title="Compare Strategies">
          <div className="mb-3 flex flex-wrap gap-2">
            {strategyStats.map((s) => (
              <button
                key={s.name}
                onClick={() => toggleStrategy(s.name)}
                className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                  selectedStrategies.includes(s.name)
                    ? 'bg-[var(--accent-blue)]/15 text-[var(--accent-blue)] ring-1 ring-[var(--accent-blue)]/30'
                    : 'bg-[var(--bg-tertiary)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
                }`}
              >
                {s.name}
              </button>
            ))}
            <span className="self-center text-[10px] text-[var(--text-secondary)]">
              Select up to 2 to compare
            </span>
          </div>

          {/* Comparison cards */}
          {comparedStats.length > 0 && (
            <div className="grid gap-4 md:grid-cols-2">
              {comparedStats.map((s) => {
                const conf = confidenceFromCount(s.tradeCount);
                const confColor = conf === 'low' ? 'text-[var(--accent-red)]'
                  : conf === 'medium' ? 'text-[var(--accent-yellow)]'
                    : 'text-[var(--accent-green)]';

                return (
                  <div key={s.name} className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
                    <div className="mb-3 flex items-center justify-between">
                      <h4 className="text-sm font-semibold text-[var(--text-primary)]">{s.name}</h4>
                      <span className={`text-[10px] font-medium ${confColor}`}>{conf}</span>
                    </div>
                    <div className="space-y-2 text-xs">
                      <MetricRow label="Total P&L" value={`${s.totalPnl >= 0 ? '+' : ''}$${s.totalPnl.toFixed(2)}`} color={s.totalPnl >= 0 ? 'green' : 'red'} />
                      <MetricRow label="Trades" value={String(s.tradeCount)} />
                      <MetricRow label="Win Rate" value={`${(s.winRate * 100).toFixed(0)}%`} color={s.winRate >= 0.5 ? 'green' : 'red'} />
                      <MetricRow label="Avg P&L" value={`$${s.avgPnl.toFixed(2)}`} color={s.avgPnl >= 0 ? 'green' : 'red'} />
                      <MetricRow label="Expectancy" value={s.expectancy != null ? `$${s.expectancy.toFixed(2)}` : '--'} color={s.expectancy != null ? (s.expectancy > 0 ? 'green' : 'red') : undefined} />
                    </div>

                    {/* Mini return distribution */}
                    {s.returns.length > 0 && (
                      <div className="mt-3">
                        <ReturnDistributionChart returns={s.returns} height={120} />
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </Section>
      )}
    </div>
  );
}

function MetricRow({ label, value, color }: { label: string; value: string; color?: 'green' | 'red' }) {
  const colorClass = color === 'green'
    ? 'text-[var(--accent-green)]'
    : color === 'red'
      ? 'text-[var(--accent-red)]'
      : 'text-[var(--text-primary)]';

  return (
    <div className="flex items-center justify-between">
      <span className="text-[var(--text-secondary)]">{label}</span>
      <span className={`font-mono font-medium ${colorClass}`}>{value}</span>
    </div>
  );
}
