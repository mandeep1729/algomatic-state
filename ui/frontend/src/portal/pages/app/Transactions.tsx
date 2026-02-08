import { useEffect, useState, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Search, ChevronLeft, ChevronRight, Filter } from 'lucide-react';
import { format } from 'date-fns';
import api from '../../api';
import { DataTable, type Column } from '../../components/DataTable';
import type { TradeSummary } from '../../types';

const SORT_OPTIONS: { label: string; value: string }[] = [
  { label: 'Newest First', value: '-entry_time' },
  { label: 'Oldest First', value: 'entry_time' },
  { label: 'Symbol A-Z', value: 'symbol' },
  { label: 'Symbol Z-A', value: '-symbol' },
];

const PAGE_SIZE = 25;

function formatDate(iso: string | null): string {
  if (!iso) return '--';
  try {
    return format(new Date(iso), 'MMM d, yyyy HH:mm');
  } catch {
    return iso;
  }
}

function formatCurrency(value: number): string {
  return `$${value.toFixed(2)}`;
}

// Define table columns for transactions
const columns: Column<TradeSummary>[] = [
  {
    key: 'date',
    header: 'Date',
    hideable: false,
    render: (trade) => (
      <span className="text-xs text-[var(--text-secondary)]">
        {formatDate(trade.entry_time)}
      </span>
    ),
  },
  {
    key: 'symbol',
    header: 'Symbol',
    hideable: false,
    render: (trade) => (
      <span className="font-medium text-[var(--accent-blue)]">
        {trade.symbol}
      </span>
    ),
  },
  {
    key: 'side',
    header: 'Side',
    render: (trade) => (
      <span
        className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${
          trade.direction === 'long'
            ? 'bg-[var(--accent-green)]/10 text-[var(--accent-green)]'
            : 'bg-[var(--accent-red)]/10 text-[var(--accent-red)]'
        }`}
      >
        {trade.direction === 'long' ? 'BUY' : 'SELL'}
      </span>
    ),
  },
  {
    key: 'quantity',
    header: 'Quantity',
    render: (trade) => (
      <span className="text-[var(--text-secondary)]">{trade.quantity}</span>
    ),
  },
  {
    key: 'price',
    header: 'Price',
    render: (trade) => (
      <span className="font-mono text-xs text-[var(--text-secondary)]">
        {formatCurrency(trade.entry_price)}
      </span>
    ),
  },
  {
    key: 'broker',
    header: 'Broker',
    render: (trade) => (
      <span className="text-xs text-[var(--text-secondary)]">
        {trade.brokerage || '-'}
      </span>
    ),
  },
];

export default function Transactions() {
  const [searchParams, setSearchParams] = useSearchParams();

  // Read filters from URL params
  const symbolFilter = searchParams.get('symbol') ?? '';
  const uncategorizedFilter = searchParams.get('uncategorized') === 'true';
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

  const toggleUncategorized = useCallback(() => {
    updateParam('uncategorized', uncategorizedFilter ? '' : 'true');
  }, [uncategorizedFilter, updateParam]);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      try {
        const res = await api.fetchTrades({
          symbol: symbolFilter || undefined,
          uncategorized: uncategorizedFilter || undefined,
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
  }, [symbolFilter, uncategorizedFilter, sortField, currentPage]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="p-6">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Transactions</h1>
        <span className="text-sm text-[var(--text-secondary)]">
          {total} fill{total !== 1 ? 's' : ''}
        </span>
      </div>

      {/* Filters bar */}
      <div className="mb-4 flex flex-wrap items-center gap-3">
        {/* Symbol search */}
        <div className="relative">
          <Search
            size={13}
            className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--text-secondary)]"
          />
          <input
            type="text"
            placeholder="Search symbol..."
            value={symbolFilter}
            onChange={(e) => updateParam('symbol', e.target.value)}
            className="h-8 w-40 rounded-md border border-[var(--border-color)] bg-[var(--bg-primary)] pl-8 pr-3 text-xs text-[var(--text-primary)] placeholder:text-[var(--text-secondary)] focus:border-[var(--accent-blue)] focus:outline-none"
          />
        </div>

        {/* Uncategorized toggle */}
        <button
          onClick={toggleUncategorized}
          className={`flex h-8 items-center gap-1.5 rounded-md border px-3 text-xs transition-colors ${
            uncategorizedFilter
              ? 'border-[var(--accent-yellow)] bg-[var(--accent-yellow)]/10 text-[var(--accent-yellow)]'
              : 'border-[var(--border-color)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
          }`}
        >
          <Filter size={13} />
          Uncategorized Only
        </button>

        {/* Sort */}
        <select
          value={sortField}
          onChange={(e) => updateParam('sort', e.target.value)}
          className="ml-auto h-8 rounded-md border border-[var(--border-color)] bg-[var(--bg-primary)] px-2 text-xs text-[var(--text-primary)] focus:border-[var(--accent-blue)] focus:outline-none"
        >
          {SORT_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      {/* DataTable with column visibility persistence */}
      <DataTable
        tableName="transactions"
        columns={columns}
        data={trades}
        loading={loading}
        emptyMessage={
          uncategorizedFilter
            ? 'All trade fills have been categorized.'
            : 'No trade fills match your search.'
        }
        getRowKey={(trade) => trade.id}
      />

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
              className="inline-flex items-center gap-1 rounded-md border border-[var(--border-color)] px-3 py-1.5 text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-primary)] disabled:cursor-not-allowed disabled:opacity-40"
            >
              <ChevronLeft size={13} />
              Previous
            </button>
            <button
              disabled={currentPage >= totalPages}
              onClick={() => updateParam('page', String(currentPage + 1))}
              className="inline-flex items-center gap-1 rounded-md border border-[var(--border-color)] px-3 py-1.5 text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-primary)] disabled:cursor-not-allowed disabled:opacity-40"
            >
              Next
              <ChevronRight size={13} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
