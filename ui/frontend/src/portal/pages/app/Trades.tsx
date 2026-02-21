import { useEffect, useState, useCallback, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { AlertTriangle, Search, ChevronLeft, ChevronRight, X } from 'lucide-react';
import api, { fetchOHLCVData, fetchFeatures, fetchSyncStatus, triggerSync } from '../../api';
import type { TradeSummary, TickerPnlSummary, PnlTimeseries } from '../../types';
import { DirectionBadge, SourceBadge, StatusBadge } from '../../components/badges';
import { OHLCVChart } from '../../../components/OHLCVChart';
import { useChartContext } from '../../context/ChartContext';
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

  // Chart state
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);
  const selectedTickerRef = useRef<string | null>(null);
  const [chartTimeframe, setChartTimeframe] = useState('15Min');
  const [ohlcvData, setOhlcvData] = useState<{ timestamps: string[]; open: number[]; high: number[]; low: number[]; close: number[]; volume: number[] } | null>(null);
  const [featureData, setFeatureData] = useState<{ timestamps: string[]; features: Record<string, number[]>; feature_names: string[] } | null>(null);
  const [chartLoading, setChartLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [tickerPnl, setTickerPnl] = useState<TickerPnlSummary | null>(null);
  const [pnlTimeseries, setPnlTimeseries] = useState<PnlTimeseries | null>(null);

  const { setChartActive, setFeatureNames, selectedFeatures } = useChartContext();

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

  // When a ticker is selected for the chart, use it as the symbol filter for the table
  const effectiveSymbolFilter = selectedTicker ?? symbolFilter;

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      try {
        const res = await api.fetchTrades({
          source: sourceFilter || undefined,
          status: statusFilter || undefined,
          symbol: effectiveSymbolFilter || undefined,
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
  }, [sourceFilter, statusFilter, effectiveSymbolFilter, flaggedFilter, sortField, currentPage]);

  // Load chart data with sync via MessageBus (same pattern as Overview)
  const loadChartData = useCallback(async (symbol: string, timeframe: string) => {
    selectedTickerRef.current = symbol;
    setChartLoading(true);
    setChartActive(true);

    const STALE_MS = 15 * 60 * 1000; // 15 minutes
    const CHART_LIMIT = 7200;

    // Helper: fetch OHLCV + features from backend (limited to CHART_LIMIT bars)
    async function fetchChartData() {
      const [ohlcv, features] = await Promise.all([
        fetchOHLCVData(symbol, timeframe, undefined, undefined, CHART_LIMIT),
        fetchFeatures(symbol, timeframe, undefined, undefined, CHART_LIMIT),
      ]);
      return { ohlcv, features };
    }

    // Helper: fetch PnL timeseries using OHLCV data
    async function loadPnlTimeseries(ohlcv: { timestamps: string[]; close: number[] }) {
      try {
        const pnl = await api.fetchTickerPnlTimeseries(symbol, ohlcv.timestamps, ohlcv.close);
        if (selectedTickerRef.current === symbol) {
          setPnlTimeseries(pnl);
        }
      } catch {
        setPnlTimeseries(null);
      }
    }

    // 1. Immediately render with whatever data the DB already has
    try {
      const { ohlcv, features } = await fetchChartData();
      setOhlcvData(ohlcv);
      setFeatureData(features);
      setFeatureNames(features.feature_names);
      loadPnlTimeseries(ohlcv);
    } catch {
      setOhlcvData(null);
      setFeatureData(null);
      setFeatureNames([]);
      setPnlTimeseries(null);
      setChartLoading(false);
      return; // No backend available
    }
    setChartLoading(false);

    // 2. Background: check sync status and trigger sync via MessageBus if stale
    try {
      const syncEntries = await fetchSyncStatus(symbol);
      const entry = syncEntries.find((e) => e.timeframe === timeframe);
      const isStale =
        !entry ||
        !entry.last_synced_timestamp ||
        Date.now() - new Date(entry.last_synced_timestamp).getTime() > STALE_MS;

      if (isStale) {
        setSyncing(true);
        await triggerSync(symbol, timeframe); // Publishes MARKET_DATA_REQUEST via MessageBus

        // Guard: user may have clicked a different ticker while sync was in flight
        if (selectedTickerRef.current !== symbol) return;

        // Re-fetch with the newly synced data
        const { ohlcv, features } = await fetchChartData();
        setOhlcvData(ohlcv);
        setFeatureData(features);
        setFeatureNames(features.feature_names);
        loadPnlTimeseries(ohlcv);
      }
    } catch {
      // Sync failed — chart already shows existing data, nothing to do
    } finally {
      setSyncing(false);
    }
  }, [setChartActive, setFeatureNames]);

  // Handle ticker click to load chart
  const handleTickerClick = useCallback(async (symbol: string, event: React.MouseEvent) => {
    event.stopPropagation(); // Prevent row click navigation
    if (selectedTicker === symbol) return;
    setSelectedTicker(symbol);
    loadChartData(symbol, chartTimeframe);
    // Fetch running PnL for this ticker
    try {
      const pnl = await api.fetchTickerPnl(symbol);
      setTickerPnl(pnl);
    } catch {
      setTickerPnl(null);
    }
  }, [selectedTicker, chartTimeframe, loadChartData]);

  const handleCloseChart = useCallback(() => {
    setSelectedTicker(null);
    selectedTickerRef.current = null;
    setOhlcvData(null);
    setFeatureData(null);
    setChartActive(false);
    setFeatureNames([]);
    setTickerPnl(null);
    setPnlTimeseries(null);
  }, [setChartActive, setFeatureNames]);

  const handleTimeframeChange = useCallback(async (newTimeframe: string) => {
    setChartTimeframe(newTimeframe);
    if (!selectedTicker) return;
    loadChartData(selectedTicker, newTimeframe);
  }, [selectedTicker, loadChartData]);

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
        <div className="relative">
          <Search size={13} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--text-secondary)]" />
          <input
            type="text"
            placeholder="Search symbol..."
            value={symbolFilter}
            onChange={(e) => updateParam('symbol', e.target.value)}
            className="h-8 w-40 rounded-md border border-[var(--border-color)] bg-[var(--bg-primary)] pl-8 pr-3 text-xs text-[var(--text-primary)] placeholder:text-[var(--text-secondary)] focus:border-[var(--accent-blue)] focus:outline-none"
          />
        </div>

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
          className={`flex h-8 items-center gap-1.5 rounded-md border px-3 text-xs transition-colors ${flaggedFilter === 'true'
              ? 'border-[var(--accent-red)] bg-[var(--accent-red)]/10 text-[var(--accent-red)]'
              : 'border-[var(--border-color)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
            }`}
        >
          <AlertTriangle size={13} />
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

      {/* OHLCV Chart (shown when a ticker is selected) */}
      {selectedTicker && (
        <div className="mb-6">
          <div className="overflow-hidden rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)]">
            <div className="flex items-center justify-between border-b border-[var(--border-color)] px-4 py-2.5">
              <div className="flex items-center gap-2">
                <span className="text-sm font-semibold text-[var(--accent-blue)]">{selectedTicker}</span>
                <select
                  value={chartTimeframe}
                  onChange={(e) => handleTimeframeChange(e.target.value)}
                  disabled={chartLoading}
                  className="h-6 rounded border border-[var(--border-color)] bg-[var(--bg-primary)] px-1.5 text-xs text-[var(--text-primary)] focus:border-[var(--accent-blue)] focus:outline-none"
                >
                  <option value="1Min">1m</option>
                  <option value="15Min">15m</option>
                  <option value="1Hour">1h</option>
                  <option value="1Day">1d</option>
                </select>
                {syncing && <span className="text-[10px] text-[var(--accent-yellow)]">Syncing...</span>}
                {tickerPnl && tickerPnl.closed_count > 0 && (
                  <span className="ml-1 flex items-center gap-1.5 rounded border border-[var(--border-color)] bg-[var(--bg-primary)] px-2 py-0.5 text-xs">
                    <span className="text-[var(--text-secondary)]">PnL:</span>
                    <span className={`font-mono font-medium ${tickerPnl.total_pnl >= 0 ? 'text-[var(--accent-green)]' : 'text-[var(--accent-red)]'}`}>
                      {tickerPnl.total_pnl >= 0 ? '+' : ''}${tickerPnl.total_pnl.toFixed(2)}
                    </span>
                    <span className={`font-mono ${tickerPnl.total_pnl_pct >= 0 ? 'text-[var(--accent-green)]' : 'text-[var(--accent-red)]'}`}>
                      ({tickerPnl.total_pnl_pct >= 0 ? '+' : ''}{tickerPnl.total_pnl_pct.toFixed(2)}%)
                    </span>
                    <span className="text-[var(--text-secondary)]">{tickerPnl.closed_count} trade{tickerPnl.closed_count !== 1 ? 's' : ''}</span>
                  </span>
                )}
              </div>
              <button
                onClick={handleCloseChart}
                className="flex h-6 w-6 items-center justify-center rounded text-[var(--text-secondary)] transition-colors duration-150 hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-primary)]"
                title="Close chart"
              >
                <X size={14} />
              </button>
            </div>
            <div className="p-2">
              {chartLoading ? (
                <div className="flex h-[400px] items-center justify-center text-sm text-[var(--text-secondary)]">
                  Loading chart data...
                </div>
              ) : ohlcvData ? (
                <OHLCVChart
                  data={ohlcvData}
                  featureData={featureData}
                  pnlData={pnlTimeseries}
                  selectedFeatures={selectedFeatures}
                  showVolume={true}
                  showStates={false}
                  height={400}
                />
              ) : (
                <div className="flex h-[400px] items-center justify-center text-sm text-[var(--text-secondary)]">
                  No chart data available for {selectedTicker}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Table */}
      <div className="overflow-hidden rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)]">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--border-color)] text-left text-xs font-medium uppercase tracking-wider text-[var(--text-secondary)]">
              <th className="px-6 py-4">Symbol</th>
              <th className="px-6 py-4">Direction</th>
              <th className="px-6 py-4">Entry</th>
              <th className="px-6 py-4">Exit</th>
              <th className="px-6 py-4">Qty</th>
              <th className="px-6 py-4">Source</th>
              <th className="px-6 py-4">Status</th>
              <th className="px-6 py-4">Flags</th>
              <th className="px-6 py-4">Time</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--border-color)]">
            {loading ? (
              <tr>
                <td colSpan={9} className="px-6 py-12 text-center text-[var(--text-secondary)]">
                  Loading...
                </td>
              </tr>
            ) : trades.length === 0 ? (
              <tr>
                <td colSpan={9} className="px-6 py-12 text-center text-[var(--text-secondary)]">
                  {selectedTicker
                    ? `No trades found for ${selectedTicker}.`
                    : 'No trades match your filters.'}
                </td>
              </tr>
            ) : (
              trades.map((trade) => (
                <tr
                  key={trade.id}
                  onClick={() => navigate(`/app/trades/${trade.id}`)}
                  className="cursor-pointer transition-colors hover:bg-[var(--bg-tertiary)]/50"
                >
                  <td className="px-6 py-4">
                    <button
                      onClick={(e) => handleTickerClick(trade.symbol, e)}
                      className={`font-medium hover:underline ${selectedTicker === trade.symbol
                          ? 'text-[var(--accent-green)]'
                          : 'text-[var(--accent-blue)]'
                        }`}
                    >
                      {trade.symbol}
                    </button>
                  </td>
                  <td className="px-6 py-4">
                    <DirectionBadge direction={trade.direction} />
                  </td>
                  <td className="px-6 py-4 font-mono text-xs text-[var(--text-secondary)]">${trade.entry_price.toFixed(2)}</td>
                  <td className="px-6 py-4 font-mono text-xs text-[var(--text-secondary)]">
                    {trade.exit_price != null ? `$${trade.exit_price.toFixed(2)}` : '--'}
                  </td>
                  <td className="px-6 py-4 text-[var(--text-secondary)]">{trade.quantity}</td>
                  <td className="px-6 py-4">
                    <SourceBadge source={trade.source} />
                  </td>
                  <td className="px-6 py-4">
                    <StatusBadge status={trade.status} />
                  </td>
                  <td className="px-6 py-4">
                    {trade.is_flagged ? (
                      <span className="inline-flex items-center gap-1 rounded-full bg-[var(--accent-red)]/10 px-2.5 py-1 text-xs font-medium text-[var(--accent-red)]">
                        {trade.flag_count} Flags
                      </span>
                    ) : (
                      <span className="text-[var(--text-secondary)]">-</span>
                    )}
                  </td>
                  <td className="px-6 py-4 text-xs text-[var(--text-secondary)]">
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
              className="inline-flex items-center gap-1 rounded-md border border-[var(--border-color)] px-3 py-1.5 text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-primary)] disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <ChevronLeft size={13} />
              Previous
            </button>
            <button
              disabled={currentPage >= totalPages}
              onClick={() => updateParam('page', String(currentPage + 1))}
              className="inline-flex items-center gap-1 rounded-md border border-[var(--border-color)] px-3 py-1.5 text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-primary)] disabled:opacity-40 disabled:cursor-not-allowed"
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


