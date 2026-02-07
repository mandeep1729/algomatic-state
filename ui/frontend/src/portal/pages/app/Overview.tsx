import { useEffect, useState, useCallback, useRef } from 'react';
import { Link } from 'react-router-dom';
import { X } from 'lucide-react';
import api, { fetchSyncStatus, triggerSync, fetchOHLCVData, fetchFeatures, fetchMockOHLCVData, fetchMockFeatures } from '../../api';
import type { TradeSummary, InsightsSummary, BrokerStatus, JournalEntry, BehavioralInsight, TickerPnlSummary, PnlTimeseries } from '../../types';
import { DirectionBadge } from '../../components/badges';
import { OHLCVChart } from '../../../components/OHLCVChart';
import { useChartContext } from '../../context/ChartContext';
import { format } from 'date-fns';

export default function Overview() {
  const [recentTrades, setRecentTrades] = useState<TradeSummary[]>([]);
  const [insights, setInsights] = useState<InsightsSummary | null>(null);
  const [brokerStatus, setBrokerStatus] = useState<BrokerStatus | null>(null);
  const [journalEntries, setJournalEntries] = useState<JournalEntry[]>([]);
  const [behavioralInsights, setBehavioralInsights] = useState<BehavioralInsight[]>([]);
  const [loading, setLoading] = useState(true);

  // Chart state
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);
  const [chartTimeframe, setChartTimeframe] = useState('5Min');
  const [ohlcvData, setOhlcvData] = useState<{ timestamps: string[]; open: number[]; high: number[]; low: number[]; close: number[]; volume: number[] } | null>(null);
  const [featureData, setFeatureData] = useState<{ timestamps: string[]; features: Record<string, number[]>; feature_names: string[] } | null>(null);
  const [chartLoading, setChartLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [tickerPnl, setTickerPnl] = useState<TickerPnlSummary | null>(null);
  const [pnlTimeseries, setPnlTimeseries] = useState<PnlTimeseries | null>(null);
  const selectedTickerRef = useRef<string | null>(null);

  const { setChartActive, setFeatureNames, selectedFeatures } = useChartContext();

  useEffect(() => {
    async function load() {
      try {
        const [tradesRes, insightsRes, brokerRes, journalRes, behavioralRes] = await Promise.all([
          api.fetchTrades({ limit: 5, sort: '-entry_time' }),
          api.fetchInsightsSummary(),
          api.fetchBrokerStatus(),
          api.fetchJournalEntries(),
          api.fetchBehavioralInsights(),
        ]);
        setRecentTrades(tradesRes.trades);
        setInsights(insightsRes);
        setBrokerStatus(brokerRes);
        setJournalEntries(journalRes);
        setBehavioralInsights(behavioralRes);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  // Re-fetch trades filtered by selectedTicker (or all when cleared)
  useEffect(() => {
    async function loadTrades() {
      try {
        const res = await api.fetchTrades({
          limit: 5,
          sort: '-entry_time',
          symbol: selectedTicker ?? undefined,
        });
        setRecentTrades(res.trades);
      } catch {
        // keep existing trades on error
      }
    }
    loadTrades();
  }, [selectedTicker]);

  const loadChartData = useCallback(async (symbol: string, timeframe: string) => {
    selectedTickerRef.current = symbol;
    setChartLoading(true);
    setChartActive(true);

    const STALE_MS = 15 * 60 * 1000; // 15 minutes

    // Helper: fetch OHLCV + features from backend
    async function fetchChartData() {
      const [ohlcv, features] = await Promise.all([
        fetchOHLCVData(symbol, timeframe),
        fetchFeatures(symbol, timeframe),
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
      // Backend unavailable — fall back to mocks for immediate render
      try {
        const [ohlcv, features] = await Promise.all([
          fetchMockOHLCVData(symbol),
          fetchMockFeatures(symbol),
        ]);
        setOhlcvData(ohlcv);
        setFeatureData(features);
        setFeatureNames(features.feature_names);
        loadPnlTimeseries(ohlcv);
      } catch {
        setOhlcvData(null);
        setFeatureData(null);
        setFeatureNames([]);
        setPnlTimeseries(null);
      }
      setChartLoading(false);
      return; // No backend — nothing to sync
    }
    setChartLoading(false);

    // 2. Background: check sync status and refresh chart if new data arrives
    try {
      const syncEntries = await fetchSyncStatus(symbol);
      const entry = syncEntries.find((e) => e.timeframe === timeframe);
      const isStale =
        !entry ||
        !entry.last_synced_timestamp ||
        Date.now() - new Date(entry.last_synced_timestamp).getTime() > STALE_MS;

      if (isStale) {
        setSyncing(true);
        await triggerSync(symbol, timeframe);

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

  const handleTickerClick = useCallback(async (symbol: string) => {
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

  const handleTimeframeChange = useCallback((newTimeframe: string) => {
    setChartTimeframe(newTimeframe);
    if (selectedTicker) {
      loadChartData(selectedTicker, newTimeframe);
    }
  }, [selectedTicker, loadChartData]);

  const handleCloseChart = useCallback(() => {
    setSelectedTicker(null);
    selectedTickerRef.current = null;
    setOhlcvData(null);
    setFeatureData(null);
    setChartActive(false);
    setFeatureNames([]);
    setSyncing(false);
    setTickerPnl(null);
    setPnlTimeseries(null);
  }, [setChartActive, setFeatureNames]);

  if (loading) {
    return <div className="p-8 text-[var(--text-secondary)]">Loading...</div>;
  }

  // Compute journal streak (consecutive days with entries, ending today or most recent)
  const journalDates = [...new Set(journalEntries.map((e) => e.date))].sort().reverse();
  const journalStreak = journalDates.length;

  return (
    <div className="p-6">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Overview</h1>
        <Link
          to="/app/evaluate"
          className="rounded-md bg-[var(--accent-blue)] px-4 py-2 text-sm font-medium text-white hover:opacity-90"
        >
          Evaluate a Trade
        </Link>
      </div>

      {/* Stats row */}
      <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <StatCard label="Total Trades" value={insights?.total_trades ?? 0} />
        <StatCard
          label="Evaluated"
          value={insights?.total_evaluated ?? 0}
          sub={insights ? `${Math.round(((insights.total_evaluated) / Math.max(insights.total_trades, 1)) * 100)}%` : undefined}
        />
        <StatCard
          label="Flagged"
          value={insights?.flagged_count ?? 0}
          accent={insights?.flagged_count ? 'red' : undefined}
        />
        <StatCard
          label="Blockers"
          value={insights?.blocker_count ?? 0}
          accent={insights?.blocker_count ? 'red' : undefined}
        />
        <StatCard
          label="Win Rate"
          value={insights?.win_rate != null ? `${(insights.win_rate * 100).toFixed(0)}%` : '--'}
          accent={insights?.win_rate != null ? (insights.win_rate >= 0.5 ? 'green' : 'red') : undefined}
        />
        <StatCard
          label="Avg R:R"
          value={insights?.avg_risk_reward?.toFixed(2) ?? '--'}
          accent={insights?.avg_risk_reward != null ? (insights.avg_risk_reward >= 1.5 ? 'green' : 'yellow') : undefined}
        />
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

      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        {/* Left column */}
        <div className="space-y-6">
          {/* Recent trades */}
          <Section title={selectedTicker ? `Recent Trades — ${selectedTicker}` : 'Recent Trades'} action={{ label: 'View All', to: '/app/trades' }}>
            <div className="overflow-hidden rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] shadow-sm">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[var(--border-color)] text-left text-xs font-medium uppercase tracking-wider text-[var(--text-secondary)]">
                    <th className="px-6 py-4">Time</th>
                    <th className="px-6 py-4">Symbol</th>
                    <th className="px-6 py-4">Dir</th>
                    <th className="px-6 py-4">Qty</th>
                    <th className="px-6 py-4">Entry</th>
                    <th className="px-6 py-4">Broker</th>
                    <th className="px-6 py-4">Flags</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border-color)]">
                  {recentTrades.map((trade) => (
                      <tr key={trade.id} className="transition-colors hover:bg-[var(--bg-tertiary)]/50">
                        <td className="px-6 py-4 text-xs text-[var(--text-secondary)]">
                          {format(new Date(trade.entry_time), 'MMM d, HH:mm')}
                        </td>
                        <td className="px-6 py-4">
                          <button
                            onClick={() => handleTickerClick(trade.symbol)}
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
                        <td className="px-6 py-4 text-[var(--text-secondary)]">{trade.quantity}</td>
                        <td className="px-6 py-4 font-mono text-xs text-[var(--text-secondary)]">${trade.entry_price.toFixed(2)}</td>
                        <td className="px-6 py-4 text-xs text-[var(--text-secondary)]">
                          {trade.brokerage ?? '--'}
                        </td>
                        <td className="px-6 py-4">
                          {trade.is_flagged ? (
                            <span className="rounded-full bg-[var(--accent-red)]/10 px-2.5 py-1 text-xs font-medium text-[var(--accent-red)]">
                              {trade.flag_count} Flags
                            </span>
                          ) : (
                            <span className="text-[var(--text-secondary)]">-</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                  {recentTrades.length === 0 && (
                    <tr>
                      <td colSpan={7} className="px-6 py-12 text-center text-sm text-[var(--text-secondary)]">
                        {selectedTicker
                          ? `No trades found for ${selectedTicker}.`
                          : <>No trades yet. <Link to="/app/evaluate" className="text-[var(--accent-blue)] hover:underline">Evaluate your first trade</Link></>
                        }
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </Section>

          {/* Top behavioral patterns */}
          <Section title="Top Behavioral Patterns" action={{ label: 'View Insights', to: '/app/insights' }}>
            {behavioralInsights.length > 0 ? (
              <div className="space-y-2">
                {behavioralInsights.slice(0, 4).map((bi) => (
                  <div
                    key={bi.signal}
                    className="flex items-center justify-between rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] px-4 py-3"
                  >
                    <div>
                      <span className="text-sm font-medium">{bi.signal.replace(/_/g, ' ')}</span>
                      <span className="ml-2 text-xs text-[var(--text-secondary)]">
                        {bi.occurrence_count}x ({bi.pct_of_trades}% of trades)
                      </span>
                    </div>
                    {bi.avg_outcome_pct != null && (
                      <span className={`font-mono text-xs font-medium ${bi.avg_outcome_pct >= 0 ? 'text-[var(--accent-green)]' : 'text-[var(--accent-red)]'}`}>
                        {bi.avg_outcome_pct > 0 ? '+' : ''}{bi.avg_outcome_pct.toFixed(2)}%
                      </span>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-[var(--text-secondary)]">No behavioral patterns tracked yet.</p>
            )}
          </Section>
        </div>

        {/* Right column — sidebar cards */}
        <div className="space-y-6">
          {/* Most common flag */}
          {insights?.most_common_flag && (
            <div className="rounded-lg border border-[var(--accent-yellow)]/30 bg-[var(--accent-yellow)]/5 p-4">
              <div className="mb-1 text-xs font-medium text-[var(--accent-yellow)]">Most Common Flag</div>
              <div className="text-sm font-medium">{insights.most_common_flag.replace(/_/g, ' ')}</div>
              <div className="mt-1 text-xs text-[var(--text-secondary)]">
                Focus on reducing this pattern to improve your results.
              </div>
            </div>
          )}

          {/* Broker connection */}
          <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
            <div className="mb-2 text-xs font-medium text-[var(--text-secondary)]">Broker Connection</div>
            {brokerStatus?.connected ? (
              <div className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-[var(--accent-green)]" />
                <span className="text-sm">{brokerStatus.brokerages.join(', ')}</span>
              </div>
            ) : (
              <div>
                <span className="text-sm text-[var(--text-secondary)]">Not connected</span>
                <Link to="/app/settings/brokers" className="mt-1 block text-xs text-[var(--accent-blue)] hover:underline">
                  Connect a broker
                </Link>
              </div>
            )}
          </div>

          {/* Journal streak */}
          <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
            <div className="mb-2 text-xs font-medium text-[var(--text-secondary)]">Journal</div>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-semibold">{journalStreak}</span>
              <span className="text-sm text-[var(--text-secondary)]">entries</span>
            </div>
            {journalEntries.length > 0 && (
              <div className="mt-1 text-xs text-[var(--text-secondary)]">
                Last entry: {format(new Date(journalEntries[0].created_at), 'MMM d')}
              </div>
            )}
            <Link to="/app/journal" className="mt-2 block text-xs text-[var(--accent-blue)] hover:underline">
              Open Journal
            </Link>
          </div>

          {/* Avg evaluation score */}
          {insights && (
            <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
              <div className="mb-2 text-xs font-medium text-[var(--text-secondary)]">Avg Evaluation Score</div>
              <div className="flex items-baseline gap-2">
                <span className={`text-2xl font-semibold ${insights.avg_score >= 70 ? 'text-[var(--accent-green)]' : insights.avg_score >= 50 ? 'text-[var(--accent-yellow)]' : 'text-[var(--accent-red)]'}`}>
                  {insights.avg_score}
                </span>
                <span className="text-sm text-[var(--text-secondary)]">/ 100</span>
              </div>
              <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-[var(--bg-primary)]">
                <div
                  className={`h-full rounded-full ${insights.avg_score >= 70 ? 'bg-[var(--accent-green)]' : insights.avg_score >= 50 ? 'bg-[var(--accent-yellow)]' : 'bg-[var(--accent-red)]'}`}
                  style={{ width: `${insights.avg_score}%` }}
                />
              </div>
            </div>
          )}

          {/* Period */}
          {insights?.period && (
            <div className="text-xs text-[var(--text-secondary)]">
              Data from {insights.period.start} to {insights.period.end}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// --- Sub-components ---

function StatCard({
  label,
  value,
  sub,
  accent,
}: {
  label: string;
  value: string | number;
  sub?: string;
  accent?: 'red' | 'green' | 'yellow';
}) {
  const colorClass = accent === 'red'
    ? 'text-[var(--accent-red)]'
    : accent === 'green'
      ? 'text-[var(--accent-green)]'
      : accent === 'yellow'
        ? 'text-[var(--accent-yellow)]'
        : 'text-[var(--text-primary)]';

  return (
    <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] px-4 py-3">
      <div className="text-[10px] font-medium uppercase tracking-wider text-[var(--text-secondary)]">{label}</div>
      <div className="mt-1 flex items-baseline gap-1.5">
        <span className={`text-xl font-semibold ${colorClass}`}>{value}</span>
        {sub && <span className="text-xs text-[var(--text-secondary)]">{sub}</span>}
      </div>
    </div>
  );
}

function Section({
  title,
  action,
  children,
}: {
  title: string;
  action?: { label: string; to: string };
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-lg font-medium">{title}</h2>
        {action && (
          <Link to={action.to} className="text-xs text-[var(--accent-blue)] hover:underline">
            {action.label}
          </Link>
        )}
      </div>
      {children}
    </div>
  );
}
