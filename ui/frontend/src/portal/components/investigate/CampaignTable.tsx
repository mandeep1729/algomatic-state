/**
 * CampaignTable — sortable table of campaigns for the Trade Explorer.
 * Click a row to navigate to campaign detail.
 */

import { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowUpDown } from 'lucide-react';
import type { CampaignSummary } from '../../types';
import { computeHoldingMinutes, formatDuration } from '../../utils/dashboardMetrics';

type SortField = 'symbol' | 'direction' | 'pnl' | 'status' | 'openedAt' | 'flags';
type SortDir = 'asc' | 'desc';

interface CampaignTableProps {
  campaigns: CampaignSummary[];
  onSymbolClick?: (symbol: string) => void;
  onStrategyClick?: (strategy: string) => void;
  onFlagClick?: (flag: string) => void;
}

export function CampaignTable({
  campaigns,
  onSymbolClick,
  onStrategyClick,
  onFlagClick,
}: CampaignTableProps) {
  const navigate = useNavigate();
  const [sortField, setSortField] = useState<SortField>('openedAt');
  const [sortDir, setSortDir] = useState<SortDir>('desc');

  function handleSort(field: SortField) {
    if (sortField === field) {
      setSortDir(sortDir === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDir('desc');
    }
  }

  const sorted = useMemo(() => {
    const arr = [...campaigns];
    const dir = sortDir === 'asc' ? 1 : -1;
    arr.sort((a, b) => {
      switch (sortField) {
        case 'symbol': return dir * a.symbol.localeCompare(b.symbol);
        case 'direction': return dir * a.direction.localeCompare(b.direction);
        case 'pnl': return dir * ((a.pnlRealized ?? 0) - (b.pnlRealized ?? 0));
        case 'status': return dir * a.status.localeCompare(b.status);
        case 'openedAt': return dir * (new Date(a.openedAt).getTime() - new Date(b.openedAt).getTime());
        case 'flags': return dir * (a.keyFlags.length - b.keyFlags.length);
        default: return 0;
      }
    });
    return arr;
  }, [campaigns, sortField, sortDir]);

  const SortHeader = ({ field, label }: { field: SortField; label: string }) => (
    <button
      onClick={() => handleSort(field)}
      className="flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
    >
      {label}
      <ArrowUpDown size={10} className={sortField === field ? 'text-[var(--accent-blue)]' : 'opacity-40'} />
    </button>
  );

  if (campaigns.length === 0) {
    return (
      <div className="flex h-40 items-center justify-center text-sm text-[var(--text-secondary)]">
        No campaigns match the current filters.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-[var(--border-color)]">
      <table className="w-full text-xs">
        <thead className="border-b border-[var(--border-color)] bg-[var(--bg-tertiary)]/30">
          <tr>
            <th className="px-3 py-2 text-left"><SortHeader field="symbol" label="Symbol" /></th>
            <th className="px-3 py-2 text-left"><SortHeader field="direction" label="Dir" /></th>
            <th className="px-3 py-2 text-left">Strategy</th>
            <th className="px-3 py-2 text-right"><SortHeader field="pnl" label="P&L" /></th>
            <th className="px-3 py-2 text-left"><SortHeader field="flags" label="Flags" /></th>
            <th className="px-3 py-2 text-left">Duration</th>
            <th className="px-3 py-2 text-left"><SortHeader field="status" label="Status" /></th>
            <th className="px-3 py-2 text-left"><SortHeader field="openedAt" label="Opened" /></th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((c) => {
            const pnl = c.pnlRealized ?? 0;
            const duration = c.closedAt
              ? formatDuration(computeHoldingMinutes(c.openedAt, c.closedAt))
              : 'open';

            return (
              <tr
                key={c.campaignId}
                onClick={() => navigate(`/app/campaigns/${c.campaignId}`)}
                className="cursor-pointer border-b border-[var(--border-color)] bg-[var(--bg-secondary)] transition-colors hover:bg-[var(--bg-tertiary)]/50 last:border-0"
              >
                <td className="px-3 py-2">
                  <button
                    onClick={(e) => { e.stopPropagation(); onSymbolClick?.(c.symbol); }}
                    className="font-medium text-[var(--accent-blue)] hover:underline"
                  >
                    {c.symbol}
                  </button>
                </td>
                <td className="px-3 py-2">
                  <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${
                    c.direction === 'long'
                      ? 'bg-[var(--accent-green)]/10 text-[var(--accent-green)]'
                      : 'bg-[var(--accent-red)]/10 text-[var(--accent-red)]'
                  }`}>
                    {c.direction}
                  </span>
                </td>
                <td className="px-3 py-2">
                  <div className="flex flex-wrap gap-1">
                    {c.strategies.length > 0
                      ? c.strategies.map((s) => (
                        <button
                          key={s}
                          onClick={(e) => { e.stopPropagation(); onStrategyClick?.(s); }}
                          className="rounded bg-[var(--bg-tertiary)] px-1.5 py-0.5 text-[10px] hover:bg-[var(--accent-blue)]/10 hover:text-[var(--accent-blue)]"
                        >
                          {s}
                        </button>
                      ))
                      : <span className="text-[var(--text-secondary)]">--</span>
                    }
                  </div>
                </td>
                <td className={`px-3 py-2 text-right font-mono font-medium ${
                  pnl >= 0 ? 'text-[var(--accent-green)]' : 'text-[var(--accent-red)]'
                }`}>
                  {c.status === 'closed' ? `${pnl >= 0 ? '+' : ''}$${pnl.toFixed(2)}` : '--'}
                </td>
                <td className="px-3 py-2">
                  <div className="flex flex-wrap gap-1">
                    {c.keyFlags.length > 0
                      ? c.keyFlags.slice(0, 2).map((f) => (
                        <button
                          key={f}
                          onClick={(e) => { e.stopPropagation(); onFlagClick?.(f); }}
                          className="rounded bg-[var(--accent-yellow)]/10 px-1.5 py-0.5 text-[10px] text-[var(--accent-yellow)] hover:bg-[var(--accent-yellow)]/20"
                        >
                          {f}
                        </button>
                      ))
                      : <span className="text-[var(--text-secondary)]">--</span>
                    }
                    {c.keyFlags.length > 2 && (
                      <span className="text-[10px] text-[var(--text-secondary)]">
                        +{c.keyFlags.length - 2}
                      </span>
                    )}
                  </div>
                </td>
                <td className="px-3 py-2 text-[var(--text-secondary)]">{duration}</td>
                <td className="px-3 py-2">
                  <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${
                    c.status === 'open'
                      ? 'bg-[var(--accent-blue)]/10 text-[var(--accent-blue)]'
                      : 'bg-[var(--bg-tertiary)] text-[var(--text-secondary)]'
                  }`}>
                    {c.status}
                  </span>
                </td>
                <td className="px-3 py-2 text-[var(--text-secondary)]">
                  {new Date(c.openedAt).toLocaleDateString('en-US', {
                    month: 'short',
                    day: 'numeric',
                    year: '2-digit',
                  })}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
