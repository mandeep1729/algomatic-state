/**
 * SubsetMetrics — live metrics strip showing key stats for the filtered subset.
 * When compare mode is on, shows delta vs all campaigns.
 */

import { useInvestigate } from '../../context/InvestigateContext';
import { StatCard } from '../ui/StatCard';

function fmtPnl(v: number): string {
  return `${v >= 0 ? '+' : ''}$${v.toFixed(2)}`;
}

function fmtPct(v: number | null): string {
  if (v == null) return '--';
  return `${(v * 100).toFixed(0)}%`;
}

function fmtDelta(subset: number, all: number): string | undefined {
  const delta = subset - all;
  if (Math.abs(delta) < 0.005) return undefined;
  const sign = delta >= 0 ? '+' : '';
  return `${sign}${delta.toFixed(2)} vs all`;
}

export function SubsetMetrics() {
  const { subsetMetrics, allMetrics, compareEnabled, filters } = useInvestigate();
  const m = subsetMetrics;
  const isFiltered = filters.length > 0;

  return (
    <div className="grid grid-cols-2 gap-3 px-6 sm:grid-cols-3 lg:grid-cols-6">
      <StatCard
        label={isFiltered ? 'Subset P&L' : 'Total P&L'}
        value={fmtPnl(m.totalPnl)}
        accent={m.totalPnl >= 0 ? 'green' : 'red'}
        sub={compareEnabled ? fmtDelta(m.totalPnl, allMetrics.totalPnl) : undefined}
      />
      <StatCard
        label="Trade Count"
        value={m.tradeCount}
        sub={compareEnabled ? `${allMetrics.tradeCount} total` : undefined}
      />
      <StatCard
        label="Win Rate"
        value={fmtPct(m.winRate)}
        accent={m.winRate != null ? (m.winRate >= 0.5 ? 'green' : m.winRate >= 0.4 ? 'yellow' : 'red') : undefined}
        sub={compareEnabled && m.winRate != null && allMetrics.winRate != null ? fmtDelta(m.winRate * 100, allMetrics.winRate * 100) + '%' : undefined}
      />
      <StatCard
        label="Avg P&L"
        value={m.avgPnl != null ? fmtPnl(m.avgPnl) : '--'}
        accent={m.avgPnl != null ? (m.avgPnl >= 0 ? 'green' : 'red') : undefined}
      />
      <StatCard
        label="Max Drawdown"
        value={m.maxDrawdown !== 0 ? `$${m.maxDrawdown.toFixed(2)}` : '--'}
        accent={m.maxDrawdown < 0 ? 'red' : undefined}
      />
      <StatCard
        label="Confidence"
        value={m.confidence === 'low' ? 'Low' : m.confidence === 'medium' ? 'Medium' : 'Higher'}
        accent={m.confidence === 'low' ? 'red' : m.confidence === 'medium' ? 'yellow' : 'green'}
        sub={`${m.tradeCount} trades`}
      />
    </div>
  );
}
