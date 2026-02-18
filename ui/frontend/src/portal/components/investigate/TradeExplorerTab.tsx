/**
 * TradeExplorerTab — filter builder + campaign table + PnL by group bar chart.
 */

import { useState, useMemo } from 'react';
import { useInvestigate } from '../../context/InvestigateContext';
import { Section } from '../ui/Section';
import { CampaignTable } from './CampaignTable';
import { PnlByGroupChart, type GroupedPnl } from '../charts/PnlByGroupChart';
import { ChartHelp } from './ChartHelp';

type GroupMode = 'symbol' | 'strategy';

export function TradeExplorerTab() {
  const { subset, addFilter } = useInvestigate();
  const [groupMode, setGroupMode] = useState<GroupMode>('symbol');

  // Build grouped PnL data
  const groupedData = useMemo((): GroupedPnl[] => {
    const map = new Map<string, { totalPnl: number; tradeCount: number }>();

    for (const c of subset) {
      if (c.status !== 'closed' || c.pnlRealized == null) continue;

      const keys = groupMode === 'symbol'
        ? [c.symbol]
        : c.strategies.length > 0 ? c.strategies : ['(none)'];

      for (const key of keys) {
        const acc = map.get(key) ?? { totalPnl: 0, tradeCount: 0 };
        acc.totalPnl += c.pnlRealized;
        acc.tradeCount++;
        map.set(key, acc);
      }
    }

    return Array.from(map.entries()).map(([key, v]) => ({ key, ...v }));
  }, [subset, groupMode]);

  function handleBarClick(key: string) {
    const field = groupMode === 'symbol' ? 'symbol' : 'strategy';
    addFilter(field, 'eq', key, `${groupMode === 'symbol' ? 'Symbol' : 'Strategy'}: ${key}`, 'chart-click');
  }

  function handleSymbolClick(symbol: string) {
    addFilter('symbol', 'eq', symbol, `Symbol: ${symbol}`, 'chart-click');
  }

  function handleStrategyClick(strategy: string) {
    addFilter('strategy', 'eq', strategy, `Strategy: ${strategy}`, 'chart-click');
  }

  function handleFlagClick(flag: string) {
    addFilter('flag', 'eq', flag, `Flag: ${flag}`, 'chart-click');
  }

  return (
    <div className="space-y-6 pt-4">
      {/* Campaign Table */}
      <Section title={`Campaigns (${subset.length})`}>
        <CampaignTable
          campaigns={subset}
          onSymbolClick={handleSymbolClick}
          onStrategyClick={handleStrategyClick}
          onFlagClick={handleFlagClick}
        />
      </Section>

      {/* PnL by Group */}
      <Section title="P&L by Group">
        <div className="mb-3 flex gap-1">
          <button
            onClick={() => setGroupMode('symbol')}
            className={`rounded-md px-3 py-1 text-xs font-medium ${
              groupMode === 'symbol'
                ? 'bg-[var(--accent-blue)]/10 text-[var(--accent-blue)]'
                : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
            }`}
          >
            By Symbol
          </button>
          <button
            onClick={() => setGroupMode('strategy')}
            className={`rounded-md px-3 py-1 text-xs font-medium ${
              groupMode === 'strategy'
                ? 'bg-[var(--accent-blue)]/10 text-[var(--accent-blue)]'
                : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
            }`}
          >
            By Strategy
          </button>
        </div>
        <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-3">
          {groupedData.length > 0 ? (
            <PnlByGroupChart
              data={groupedData}
              height={260}
              onBarClick={handleBarClick}
            />
          ) : (
            <div className="flex h-[260px] items-center justify-center text-sm text-[var(--text-secondary)]">
              No closed campaigns to chart.
            </div>
          )}
        </div>
        <ChartHelp
          what={`Total P&L broken down by ${groupMode}. Green bars are profitable groups, red are losing.`}
          how="Identify which groups are dragging performance. The worst performers may need rule changes or avoidance."
          click="Click a bar to add a filter for that group and see its trades in detail."
        />
      </Section>
    </div>
  );
}
