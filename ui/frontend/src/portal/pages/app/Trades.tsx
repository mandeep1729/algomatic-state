import { useEffect, useState, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import api from '../../api';
import type { TradeSummary } from '../../types';
import { DirectionBadge, SourceBadge, StatusBadge } from '../../components/badges';
import { format } from 'date-fns';

const SOURCE_OPTIONS: { label: string; value: string }[] = [
  { label: 'All Sources', value: '' },
  { label: 'Synced', value: 'synced' },
  { label: 'Manual', value: 'manual' },
  { label: 'CSV', value: 'csv' },
  { label: 'Proposed', value: 'proposed' },
];

const STATUS_OPTIONS: { label: string; value: string }[] = [
  { label: 'All Statuses', value: '' },
  { label: 'Open', value: 'open' },
  { label: 'Closed', value: 'closed' },
  { label: 'Proposed', value: 'proposed' },
];

const SORT_OPTIONS: { label: string; value: string }[] = [
  { label: 'Newest First', value: '-entry_time' },
  { label: 'Oldest First', value: 'entry_time' },
  { label: 'Symbol A-Z', value: 'symbol' },
  { label: 'Symbol Z-A', value: '-symbol' },
];

const PAGE_SIZE = 10;

export default function Trades() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  // Read filters from URL params
  const sourceFilter = searchParams.get('source') ?? '';
  const statusFilter = searchParams.get('status') ?? '';
  const symbolFilter = searchParams.get('symbol') ?? '';
  const flaggedFilter = searchParams.get('flagged');
  const sortField = searchParams.get('sort') ?? '-entry_time';
  const currentPage = parseInt(searchParams.get('page') ?? '1', 10);

  const [trades, setTrades] = useState<TradeSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  const updateParam = useCallback(
    (key: string, value: string) => {
      const next = new URLSearchParams(searchParams);
      if (value) {
        next.set(key, value);
      } else {
        next.delete(key);
      }
      // Reset to page 1 when filters change (except when changing page itself)
      if (key !== 'page') {
        next.delete('page');
      }
      setSearchParams(next, { replace: true });
    },
    [searchParams, setSearchParams],
  );

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      try {
        const res = await api.fetchTrades({
          source: sourceFilter || undefined,
          status: statusFilter || undefined,
          symbol: symbolFilter || undefined,
          flagged: flaggedFilter === 'true' ? true : flaggedFilter === 'false' ? false : undefined,
          sort: sortField,
          page: currentPage,
          limit: PAGE_SIZE,
        });
        if (!cancelled) {
          setTrades(res.trades);
          setTotal(res.total);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => { cancelled = true; };
  }, [sourceFilter, statusFilter, symbolFilter, flaggedFilter, sortField, currentPage]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  function formatTime(iso: string | null): string {
    if (!iso) return '--';
    try {
      return format(new Date(iso), 'MMM d, yyyy HH:mm');
    } catch {
      return iso;
    }
  }

  return (
    <div className="p-6">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Trades</h1>
        <span className="text-sm text-[var(--text-secondary)]">{total} total</span>
      </div>

      {/* Filters bar */}
      <div className="mb-4 flex flex-wrap items-center gap-3">
        {/* Symbol search */}
        <input
          type="text"
          placeholder="Search symbol..."
          value={symbolFilter}
          onChange={(e) => updateParam('symbol', e.target.value)}
          className="h-8 w-40 rounded-md border border-[var(--border-color)] bg-[var(--bg-primary)] px-3 text-xs text-[var(--text-primary)] placeholder:text-[var(--text-secondary)] focus:border-[var(--accent-blue)] focus:outline-none"
        />

        {/* Source filter */}
        <select
          value={sourceFilter}
          onChange={(e) => updateParam('source', e.target.value)}
          className="h-8 rounded-md border border-[var(--border-color)] bg-[var(--bg-primary)] px-2 text-xs text-[var(--text-primary)] focus:border-[var(--accent-blue)] focus:outline-none"
        >
          {SOURCE_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>

        {/* Status filter */}
        <select
          value={statusFilter}
          onChange={(e) => updateParam('status', e.target.value)}
          className="h-8 rounded-md border border-[var(--border-color)] bg-[var(--bg-primary)] px-2 text-xs text-[var(--text-primary)] focus:border-[var(--accent-blue)] focus:outline-none"
        >
          {STATUS_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>

        {/* Flagged toggle */}
        <button
          onClick={() => {
            if (flaggedFilter === 'true') {
              updateParam('flagged', '');
            } else {
              updateParam('flagged', 'true');
            }
          }}
          className={`flex h-8 items-center gap-1.5 rounded-md border px-3 text-xs transition-colors ${
            flaggedFilter === 'true'
              ? 'border-[var(--accent-red)] bg-[var(--accent-red)]/10 text-[var(--accent-red)]'
              : 'border-[var(--border-color)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
          }`}
        >
          <span>{'\u26A0'}</span>
          Flagged Only
        </button>

        {/* Sort */}
        <select
          value={sortField}
          onChange={(e) => updateParam('sort', e.target.value)}
          className="ml-auto h-8 rounded-md border border-[var(--border-color)] bg-[var(--bg-primary)] px-2 text-xs text-[var(--text-primary)] focus:border-[var(--accent-blue)] focus:outline-none"
        >
          {SORT_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
      </div>

      {/* Table */}
      <div className="overflow-hidden rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)]">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--border-color)] text-left text-xs font-medium text-[var(--text-secondary)]">
              <th className="px-4 py-3">Symbol</th>
              <th className="px-4 py-3">Direction</th>
              <th className="px-4 py-3">Entry</th>
              <th className="px-4 py-3">Exit</th>
              <th className="px-4 py-3">Qty</th>
              <th className="px-4 py-3">Source</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Flags</th>
              <th className="px-4 py-3">Time</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={9} className="px-4 py-8 text-center text-[var(--text-secondary)]">
                  Loading...
                </td>
              </tr>
            ) : trades.length === 0 ? (
              <tr>
                <td colSpan={9} className="px-4 py-8 text-center text-[var(--text-secondary)]">
                  No trades match your filters.
                </td>
              </tr>
            ) : (
              trades.map((trade) => (
                <tr
                  key={trade.id}
                  onClick={() => navigate(`/app/trades/${trade.id}`)}
                  className="cursor-pointer border-b border-[var(--border-color)] last:border-0 hover:bg-[var(--bg-primary)] transition-colors"
                >
                  <td className="px-4 py-3 font-medium">{trade.symbol}</td>
                  <td className="px-4 py-3">
                    <DirectionBadge direction={trade.direction} />
                  </td>
                  <td className="px-4 py-3 font-mono text-xs">${trade.entry_price.toFixed(2)}</td>
                  <td className="px-4 py-3 font-mono text-xs">
                    {trade.exit_price != null ? `$${trade.exit_price.toFixed(2)}` : '--'}
                  </td>
                  <td className="px-4 py-3 text-[var(--text-secondary)]">{trade.quantity}</td>
                  <td className="px-4 py-3">
                    <SourceBadge source={trade.source} />
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={trade.status} />
                  </td>
                  <td className="px-4 py-3">
                    {trade.is_flagged ? (
                      <span className="inline-flex items-center gap-1 rounded bg-[var(--accent-red)]/10 px-2 py-0.5 text-xs text-[var(--accent-red)]">
                        {trade.flag_count}
                      </span>
                    ) : (
                      <span className="text-[var(--text-secondary)]">--</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-xs text-[var(--text-secondary)]">
                    {formatTime(trade.entry_time)}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="mt-4 flex items-center justify-between text-sm">
          <span className="text-xs text-[var(--text-secondary)]">
            Page {currentPage} of {totalPages}
          </span>
          <div className="flex gap-2">
            <button
              disabled={currentPage <= 1}
              onClick={() => updateParam('page', String(currentPage - 1))}
              className="rounded-md border border-[var(--border-color)] px-3 py-1.5 text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-primary)] disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Previous
            </button>
            <button
              disabled={currentPage >= totalPages}
              onClick={() => updateParam('page', String(currentPage + 1))}
              className="rounded-md border border-[var(--border-color)] px-3 py-1.5 text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-primary)] disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

