import { useEffect, useState, useCallback, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Search, Filter, Pencil, Loader2, X } from 'lucide-react';
import { format } from 'date-fns';
import api from '../../api';
import { bulkUpdateStrategy } from '../../api';
import { fetchStrategies } from '../../api/client';
import { mergeStrategies } from '../../utils/defaultStrategies';
import { DataTable, type Column } from '../../components/DataTable';
import { FillContextModal } from '../../components/FillContextModal';
import type { TradeSummary, StrategyDefinition } from '../../types';

const SORT_OPTIONS: { label: string; value: string }[] = [
  { label: 'Newest First', value: '-entry_time' },
  { label: 'Oldest First', value: 'entry_time' },
  { label: 'Symbol A-Z', value: 'symbol' },
  { label: 'Symbol Z-A', value: '-symbol' },
];

// Fetch trades in bulk and let DataTable handle client-side pagination
const FETCH_LIMIT = 200;

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

/** Format context summary into a compact display string */
function formatContextSummary(trade: TradeSummary): string | null {
  const ctx = trade.context_summary;
  if (!ctx) return null;

  const parts: string[] = [];
  if (ctx.strategy) parts.push(ctx.strategy);
  if (ctx.emotions) parts.push(ctx.emotions);
  if (ctx.hypothesis_snippet) parts.push(ctx.hypothesis_snippet);

  return parts.length > 0 ? parts.join(' | ') : null;
}

export default function Transactions() {
  const [searchParams, setSearchParams] = useSearchParams();

  // Read filters from URL params
  const symbolFilter = searchParams.get('symbol') ?? '';
  const uncategorizedFilter = searchParams.get('uncategorized') === 'true';
  const sortField = searchParams.get('sort') ?? '-entry_time';

  const [trades, setTrades] = useState<TradeSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  // Context modal state
  const [selectedFill, setSelectedFill] = useState<TradeSummary | null>(null);
  const [contextModalOpen, setContextModalOpen] = useState(false);

  // Bulk edit state
  const [selectedTradeIds, setSelectedTradeIds] = useState<Set<string>>(new Set());
  const [bulkStrategyId, setBulkStrategyId] = useState<string>('');
  const [strategies, setStrategies] = useState<StrategyDefinition[]>([]);
  const [mergedStrategies, setMergedStrategies] = useState<Array<{ id: string; name: string }>>(
    [],
  );
  const [strategiesLoading, setStrategiesLoading] = useState(false);
  const [bulkApplying, setBulkApplying] = useState(false);
  const [bulkError, setBulkError] = useState<string | null>(null);
  const [bulkSuccess, setBulkSuccess] = useState<string | null>(null);

  const hasSelection = selectedTradeIds.size > 0;

  const updateParam = useCallback(
    (key: string, value: string) => {
      const next = new URLSearchParams(searchParams);
      if (value) {
        next.set(key, value);
      } else {
        next.delete(key);
      }
      setSearchParams(next, { replace: true });
    },
    [searchParams, setSearchParams],
  );

  const toggleUncategorized = useCallback(() => {
    updateParam('uncategorized', uncategorizedFilter ? '' : 'true');
  }, [uncategorizedFilter, updateParam]);

  const loadTrades = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.fetchTrades({
        symbol: symbolFilter || undefined,
        uncategorized: uncategorizedFilter || undefined,
        sort: sortField,
        limit: FETCH_LIMIT,
      });
      setTrades(res.trades);
      setTotal(res.total);
    } finally {
      setLoading(false);
    }
  }, [symbolFilter, uncategorizedFilter, sortField]);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      try {
        const res = await api.fetchTrades({
          symbol: symbolFilter || undefined,
          uncategorized: uncategorizedFilter || undefined,
          sort: sortField,
          limit: FETCH_LIMIT,
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
  }, [symbolFilter, uncategorizedFilter, sortField]);

  // Load strategies when selection starts
  useEffect(() => {
    if (!hasSelection || strategies.length > 0) return;

    let cancelled = false;
    setStrategiesLoading(true);

    async function load() {
      try {
        const data = await fetchStrategies();
        if (cancelled) return;
        setStrategies(data);
        // Merge user strategies with defaults
        const merged = mergeStrategies(
          data.filter((s) => s.is_active).map((s) => ({ id: s.id, name: s.name })),
          true,
        );
        setMergedStrategies(merged);
      } catch (err) {
        console.error('[Transactions] Failed to load strategies:', err);
      } finally {
        if (!cancelled) setStrategiesLoading(false);
      }
    }

    load();
    return () => { cancelled = true; };
  }, [hasSelection, strategies.length]);

  // Handle context cell click
  const handleContextClick = useCallback((trade: TradeSummary, event: React.MouseEvent) => {
    event.stopPropagation(); // Prevent row click if any
    setSelectedFill(trade);
    setContextModalOpen(true);
  }, []);

  // Handle context save - refresh the data
  const handleContextSave = useCallback(() => {
    loadTrades();
  }, [loadTrades]);

  // Close modal
  const handleCloseModal = useCallback(() => {
    setContextModalOpen(false);
    setSelectedFill(null);
  }, []);

  // Bulk edit handlers
  const handleClearSelection = useCallback(() => {
    setSelectedTradeIds(new Set());
    setBulkStrategyId('');
    setBulkError(null);
    setBulkSuccess(null);
  }, []);

  const handleBulkApply = useCallback(async () => {
    if (!bulkStrategyId || selectedTradeIds.size === 0) return;

    setBulkApplying(true);
    setBulkError(null);
    setBulkSuccess(null);

    try {
      const fillIds = Array.from(selectedTradeIds).map((id) => parseInt(id, 10));
      const strategyId = parseInt(bulkStrategyId, 10);

      const result = await bulkUpdateStrategy({
        fill_ids: fillIds,
        strategy_id: strategyId,
      });

      const strategyName =
        mergedStrategies.find((s) => s.id === bulkStrategyId)?.name ?? 'selected strategy';
      setBulkSuccess(
        `Updated ${result.updated_count} fill${result.updated_count !== 1 ? 's' : ''} to "${strategyName}"` +
        (result.skipped_count > 0 ? ` (${result.skipped_count} skipped - not linked to campaigns)` : ''),
      );

      // Refresh table data and clear selection after a brief pause
      await loadTrades();
      setSelectedTradeIds(new Set());
      setBulkStrategyId('');
    } catch (err) {
      console.error('[Transactions] Bulk update failed:', err);
      setBulkError(err instanceof Error ? err.message : 'Failed to apply bulk update');
    } finally {
      setBulkApplying(false);
    }
  }, [bulkStrategyId, selectedTradeIds, strategies, loadTrades]);

  // Define table columns with context click handler
  // Each column includes filterFn for case-insensitive filtering on the actual data
  const columns: Column<TradeSummary>[] = useMemo(() => [
    {
      key: 'date',
      header: 'Date',
      hideable: false,
      render: (trade) => (
        <span className="text-xs text-[var(--text-secondary)]">
          {formatDate(trade.entry_time)}
        </span>
      ),
      filterFn: (trade, filterText) => {
        const formatted = formatDate(trade.entry_time);
        return formatted.toLowerCase().includes(filterText.toLowerCase());
      },
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
      filterFn: (trade, filterText) =>
        trade.symbol.toLowerCase().includes(filterText.toLowerCase()),
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
      filterFn: (trade, filterText) => {
        // Allow filtering by direction (long/short) or display value (buy/sell)
        const searchLower = filterText.toLowerCase();
        const direction = trade.direction.toLowerCase();
        const displayValue = trade.direction === 'long' ? 'buy' : 'sell';
        return direction.includes(searchLower) || displayValue.includes(searchLower);
      },
    },
    {
      key: 'quantity',
      header: 'Quantity',
      render: (trade) => (
        <span className="text-[var(--text-secondary)]">{trade.quantity}</span>
      ),
      filterFn: (trade, filterText) =>
        String(trade.quantity).includes(filterText),
    },
    {
      key: 'price',
      header: 'Price',
      render: (trade) => (
        <span className="font-mono text-xs text-[var(--text-secondary)]">
          {formatCurrency(trade.entry_price)}
        </span>
      ),
      filterFn: (trade, filterText) => {
        // Allow filtering by formatted price (e.g., "$123.45") or raw number
        const formatted = formatCurrency(trade.entry_price);
        const raw = String(trade.entry_price);
        return formatted.includes(filterText) || raw.includes(filterText);
      },
    },
    {
      key: 'broker',
      header: 'Broker',
      render: (trade) => (
        <span className="text-xs text-[var(--text-secondary)]">
          {trade.brokerage || '-'}
        </span>
      ),
      filterFn: (trade, filterText) => {
        if (!trade.brokerage) return false;
        return trade.brokerage.toLowerCase().includes(filterText.toLowerCase());
      },
    },
    {
      key: 'context',
      header: 'Context',
      render: (trade) => {
        const summary = formatContextSummary(trade);
        return (
          <button
            type="button"
            onClick={(e) => handleContextClick(trade, e)}
            className="group flex max-w-[200px] items-center gap-1.5 rounded px-1.5 py-0.5 text-left transition-colors hover:bg-[var(--bg-tertiary)]"
            title={summary || 'Click to add context'}
          >
            {summary ? (
              <span className="truncate text-xs text-[var(--text-secondary)] group-hover:text-[var(--text-primary)]">
                {summary}
              </span>
            ) : (
              <span className="text-xs text-[var(--text-secondary)] opacity-50 group-hover:opacity-100">
                Add context
              </span>
            )}
            <Pencil
              size={12}
              className="shrink-0 text-[var(--text-secondary)] opacity-0 group-hover:opacity-100 transition-opacity"
            />
          </button>
        );
      },
      filterFn: (trade, filterText) => {
        const summary = formatContextSummary(trade);
        if (!summary) return false;
        return summary.toLowerCase().includes(filterText.toLowerCase());
      },
    },
  ], [handleContextClick]);

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

      {/* Bulk edit bar - shown when trades are selected */}
      {hasSelection && (
        <div className="mb-3 flex flex-wrap items-center gap-3 rounded-lg border border-[var(--accent-blue)]/30 bg-[var(--accent-blue)]/5 px-4 py-3">
          <span className="text-sm font-medium text-[var(--text-primary)]">
            {selectedTradeIds.size} fill{selectedTradeIds.size !== 1 ? 's' : ''} selected
          </span>

          <div className="mx-1 h-5 w-px bg-[var(--border-color)]" />

          {/* Strategy dropdown */}
          <label className="flex items-center gap-2 text-xs text-[var(--text-secondary)]">
            Strategy:
            <select
              value={bulkStrategyId}
              onChange={(e) => setBulkStrategyId(e.target.value)}
              disabled={strategiesLoading || bulkApplying}
              className="h-8 min-w-[180px] rounded-md border border-[var(--border-color)] bg-[var(--bg-primary)] px-2 text-xs text-[var(--text-primary)] focus:border-[var(--accent-blue)] focus:outline-none disabled:opacity-50"
            >
              <option value="">
                {strategiesLoading ? 'Loading...' : '-- Select strategy --'}
              </option>
              {mergedStrategies.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </label>

          {/* Apply button */}
          <button
            type="button"
            onClick={handleBulkApply}
            disabled={!bulkStrategyId || bulkApplying}
            className="inline-flex h-8 items-center gap-1.5 rounded-md bg-[var(--accent-blue)] px-4 text-xs font-medium text-white transition-colors hover:bg-[var(--accent-blue)]/90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {bulkApplying && <Loader2 size={13} className="animate-spin" />}
            Apply
          </button>

          {/* Cancel button */}
          <button
            type="button"
            onClick={handleClearSelection}
            disabled={bulkApplying}
            className="inline-flex h-8 items-center gap-1 rounded-md border border-[var(--border-color)] px-3 text-xs text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-primary)] disabled:opacity-50"
          >
            <X size={13} />
            Cancel
          </button>

          {/* Error message */}
          {bulkError && (
            <span className="text-xs text-[var(--accent-red)]">{bulkError}</span>
          )}
        </div>
      )}

      {/* Success message */}
      {bulkSuccess && !hasSelection && (
        <div className="mb-3 flex items-center gap-2 rounded-lg border border-[var(--accent-green)]/30 bg-[var(--accent-green)]/5 px-4 py-2.5">
          <span className="text-xs text-[var(--accent-green)]">{bulkSuccess}</span>
          <button
            type="button"
            onClick={() => setBulkSuccess(null)}
            className="ml-auto text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
          >
            <X size={13} />
          </button>
        </div>
      )}

      {/* DataTable with column visibility persistence and selection */}
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
        selectedKeys={selectedTradeIds}
        onSelectionChange={setSelectedTradeIds}
      />

      {/* Context Edit Modal */}
      {selectedFill && (
        <FillContextModal
          isOpen={contextModalOpen}
          onClose={handleCloseModal}
          fillId={selectedFill.id}
          symbol={selectedFill.symbol}
          onSave={handleContextSave}
        />
      )}
    </div>
  );
}
