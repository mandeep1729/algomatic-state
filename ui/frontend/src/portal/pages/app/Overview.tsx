import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import api from '../../api';
import type { TradeSummary, InsightsSummary, BrokerStatus, JournalEntry, BehavioralInsight } from '../../types';
import { DirectionBadge, SourceBadge, StatusBadge } from '../../components/badges';
import { format } from 'date-fns';

export default function Overview() {
  const [recentTrades, setRecentTrades] = useState<TradeSummary[]>([]);
  const [insights, setInsights] = useState<InsightsSummary | null>(null);
  const [brokerStatus, setBrokerStatus] = useState<BrokerStatus | null>(null);
  const [journalEntries, setJournalEntries] = useState<JournalEntry[]>([]);
  const [behavioralInsights, setBehavioralInsights] = useState<BehavioralInsight[]>([]);
  const [loading, setLoading] = useState(true);

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

      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        {/* Left column */}
        <div className="space-y-6">
          {/* Recent trades */}
          <Section title="Recent Trades" action={{ label: 'View All', to: '/app/trades' }}>
            <div className="overflow-hidden rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)]">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[var(--border-color)] text-left text-xs font-medium text-[var(--text-secondary)]">
                    <th className="px-4 py-2.5">Symbol</th>
                    <th className="px-4 py-2.5">Dir</th>
                    <th className="px-4 py-2.5">Entry</th>
                    <th className="px-4 py-2.5">Source</th>
                    <th className="px-4 py-2.5">Status</th>
                    <th className="px-4 py-2.5">Flags</th>
                  </tr>
                </thead>
                <tbody>
                  {recentTrades.map((trade) => (
                    <tr key={trade.id} className="border-b border-[var(--border-color)] last:border-0 hover:bg-[var(--bg-primary)] transition-colors">
                      <td className="px-4 py-2.5">
                        <Link to={`/app/trades/${trade.id}`} className="font-medium text-[var(--accent-blue)] hover:underline">
                          {trade.symbol}
                        </Link>
                      </td>
                      <td className="px-4 py-2.5">
                        <DirectionBadge direction={trade.direction} />
                      </td>
                      <td className="px-4 py-2.5 font-mono text-xs">${trade.entry_price.toFixed(2)}</td>
                      <td className="px-4 py-2.5"><SourceBadge source={trade.source} /></td>
                      <td className="px-4 py-2.5"><StatusBadge status={trade.status} /></td>
                      <td className="px-4 py-2.5">
                        {trade.is_flagged ? (
                          <span className="rounded bg-[var(--accent-red)]/10 px-2 py-0.5 text-xs text-[var(--accent-red)]">
                            {trade.flag_count}
                          </span>
                        ) : (
                          <span className="text-[var(--text-secondary)]">--</span>
                        )}
                      </td>
                    </tr>
                  ))}
                  {recentTrades.length === 0 && (
                    <tr>
                      <td colSpan={6} className="px-4 py-6 text-center text-sm text-[var(--text-secondary)]">
                        No trades yet. <Link to="/app/evaluate" className="text-[var(--accent-blue)] hover:underline">Evaluate your first trade</Link>
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
