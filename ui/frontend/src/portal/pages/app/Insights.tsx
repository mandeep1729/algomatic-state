import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import api from '../../api';
import type {
  InsightsSummary,
  RegimeInsight,
  TimingInsight,
  BehavioralInsight,
  RiskInsight,
  StrategyDriftInsight,
} from '../../types';

const TABS = [
  { key: 'summary', label: 'Summary' },
  { key: 'regimes', label: 'Regimes' },
  { key: 'timing', label: 'Timing' },
  { key: 'behavioral', label: 'Behavioral' },
  { key: 'risk', label: 'Risk' },
  { key: 'drift', label: 'Strategy Drift' },
] as const;

type TabKey = (typeof TABS)[number]['key'];

export default function Insights() {
  const [searchParams, setSearchParams] = useSearchParams();
  const activeTab = (searchParams.get('tab') as TabKey) || 'summary';

  function setTab(tab: TabKey) {
    setSearchParams({ tab }, { replace: true });
  }

  return (
    <div className="p-6">
      <h1 className="mb-6 text-2xl font-semibold">Insights</h1>

      {/* Tab bar */}
      <div className="mb-6 flex gap-1 border-b border-[var(--border-color)]">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setTab(tab.key)}
            className={`px-4 py-2.5 text-sm transition-colors -mb-px border-b-2 ${
              activeTab === tab.key
                ? 'border-[var(--accent-blue)] text-[var(--accent-blue)]'
                : 'border-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === 'summary' && <SummaryTab />}
      {activeTab === 'regimes' && <RegimesTab />}
      {activeTab === 'timing' && <TimingTab />}
      {activeTab === 'behavioral' && <BehavioralTab />}
      {activeTab === 'risk' && <RiskTab />}
      {activeTab === 'drift' && <DriftTab />}
    </div>
  );
}

// =============================================================================
// Summary Tab
// =============================================================================

function SummaryTab() {
  const [data, setData] = useState<InsightsSummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.fetchInsightsSummary().then(setData).finally(() => setLoading(false));
  }, []);

  if (loading) return <Loading />;
  if (!data) return null;

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <SummaryCard label="Total Trades" value={data.total_trades} />
      <SummaryCard label="Evaluated" value={data.total_evaluated} sub={`${Math.round((data.total_evaluated / Math.max(data.total_trades, 1)) * 100)}%`} />
      <SummaryCard label="Flagged" value={data.flagged_count} accent={data.flagged_count > 0 ? 'red' : undefined} />
      <SummaryCard label="Blockers" value={data.blocker_count} accent={data.blocker_count > 0 ? 'red' : undefined} />
      <SummaryCard label="Avg Score" value={`${data.avg_score}/100`} accent={data.avg_score >= 70 ? 'green' : data.avg_score >= 50 ? 'yellow' : 'red'} />
      <SummaryCard label="Avg R:R" value={data.avg_risk_reward.toFixed(2)} accent={data.avg_risk_reward >= 1.5 ? 'green' : 'yellow'} />
      <SummaryCard label="Win Rate" value={data.win_rate != null ? `${(data.win_rate * 100).toFixed(0)}%` : '--'} accent={data.win_rate != null ? (data.win_rate >= 0.5 ? 'green' : 'red') : undefined} />
      <SummaryCard label="Most Common Flag" value={data.most_common_flag?.replace(/_/g, ' ') ?? 'None'} />
    </div>
  );
}

// =============================================================================
// Regimes Tab
// =============================================================================

function RegimesTab() {
  const [data, setData] = useState<RegimeInsight[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.fetchRegimeInsights().then(setData).finally(() => setLoading(false));
  }, []);

  if (loading) return <Loading />;

  return (
    <div>
      <p className="mb-4 text-sm text-[var(--text-secondary)]">
        Performance breakdown by market regime. Trades in unfavorable regimes tend to have worse outcomes.
      </p>
      <DataTable
        columns={[
          { key: 'regime_label', label: 'Regime', render: (v: string) => v.replace(/_/g, ' ') },
          { key: 'trade_count', label: 'Trades' },
          { key: 'avg_score', label: 'Avg Score', render: (v: number) => <ScoreValue value={v} /> },
          { key: 'flagged_pct', label: 'Flagged %', render: (v: number) => <PctBar value={v} color="red" /> },
          { key: 'avg_pnl_pct', label: 'Avg P&L %', render: (v: number | null) => v != null ? <PnlValue value={v} /> : '--' },
        ]}
        rows={data}
      />
    </div>
  );
}

// =============================================================================
// Timing Tab
// =============================================================================

function TimingTab() {
  const [data, setData] = useState<TimingInsight[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.fetchTimingInsights().then(setData).finally(() => setLoading(false));
  }, []);

  if (loading) return <Loading />;

  return (
    <div>
      <p className="mb-4 text-sm text-[var(--text-secondary)]">
        When you trade matters. Early morning trades often have higher flag rates due to rushed entries.
      </p>
      <DataTable
        columns={[
          { key: 'hour_of_day', label: 'Hour', render: (v: number) => `${v}:00` },
          { key: 'trade_count', label: 'Trades' },
          { key: 'avg_score', label: 'Avg Score', render: (v: number) => <ScoreValue value={v} /> },
          { key: 'flagged_pct', label: 'Flagged %', render: (v: number) => <PctBar value={v} color="red" /> },
        ]}
        rows={data}
      />
      {/* Simple hour distribution bar chart */}
      <div className="mt-6">
        <h3 className="mb-3 text-sm font-medium text-[var(--text-secondary)]">Trade Distribution by Hour</h3>
        <div className="flex items-end gap-2" style={{ height: 120 }}>
          {data.map((d) => {
            const maxCount = Math.max(...data.map((r) => r.trade_count), 1);
            const height = (d.trade_count / maxCount) * 100;
            return (
              <div key={d.hour_of_day} className="flex flex-1 flex-col items-center gap-1">
                <div
                  className={`w-full rounded-t ${d.flagged_pct > 40 ? 'bg-[var(--accent-red)]' : 'bg-[var(--accent-blue)]'}`}
                  style={{ height: `${height}%`, minHeight: 4 }}
                  title={`${d.trade_count} trades at ${d.hour_of_day}:00`}
                />
                <span className="text-[10px] text-[var(--text-secondary)]">{d.hour_of_day}</span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// Behavioral Tab
// =============================================================================

function BehavioralTab() {
  const [data, setData] = useState<BehavioralInsight[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.fetchBehavioralInsights().then(setData).finally(() => setLoading(false));
  }, []);

  if (loading) return <Loading />;

  return (
    <div>
      <p className="mb-4 text-sm text-[var(--text-secondary)]">
        Behavioral signals that recur across your trades. Reducing these patterns is the fastest way to improve.
      </p>
      <div className="space-y-3">
        {data.map((bi) => (
          <div
            key={bi.signal}
            className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4"
          >
            <div className="flex items-center justify-between">
              <div>
                <span className="text-sm font-medium">{bi.signal.replace(/_/g, ' ')}</span>
                <div className="mt-1 flex gap-4 text-xs text-[var(--text-secondary)]">
                  <span>{bi.occurrence_count} occurrences</span>
                  <span>{bi.pct_of_trades}% of trades</span>
                </div>
              </div>
              <div className="text-right">
                {bi.avg_outcome_pct != null ? (
                  <div>
                    <div className="text-xs text-[var(--text-secondary)]">Avg outcome</div>
                    <PnlValue value={bi.avg_outcome_pct} />
                  </div>
                ) : (
                  <span className="text-xs text-[var(--text-secondary)]">No outcome data</span>
                )}
              </div>
            </div>
            {/* Frequency bar */}
            <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-[var(--bg-primary)]">
              <div
                className="h-full rounded-full bg-[var(--accent-red)]"
                style={{ width: `${Math.min(bi.pct_of_trades, 100)}%` }}
              />
            </div>
          </div>
        ))}
        {data.length === 0 && (
          <p className="text-sm text-[var(--text-secondary)]">No behavioral signals recorded yet.</p>
        )}
      </div>
    </div>
  );
}

// =============================================================================
// Risk Tab
// =============================================================================

function RiskTab() {
  const [data, setData] = useState<RiskInsight[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.fetchRiskInsights().then(setData).finally(() => setLoading(false));
  }, []);

  if (loading) return <Loading />;

  return (
    <div>
      <p className="mb-4 text-sm text-[var(--text-secondary)]">
        Daily risk metric trends. Watch for days where stops are missing or positions are oversized.
      </p>
      <DataTable
        columns={[
          { key: 'date', label: 'Date', render: (v: string) => v.slice(5) },
          { key: 'avg_risk_reward', label: 'Avg R:R', render: (v: number) => v > 0 ? <ScoreValue value={v * 30} label={v.toFixed(2)} /> : <span className="text-[var(--accent-red)]">N/A</span> },
          { key: 'trades_without_stop', label: 'No Stop', render: (v: number) => v > 0 ? <span className="font-medium text-[var(--accent-red)]">{v}</span> : <span className="text-[var(--text-secondary)]">0</span> },
          { key: 'max_position_pct', label: 'Max Pos %', render: (v: number) => <PctBar value={v / 5 * 100} color={v > 2 ? 'red' : 'blue'} label={`${v.toFixed(1)}%`} /> },
        ]}
        rows={data}
      />
    </div>
  );
}

// =============================================================================
// Strategy Drift Tab
// =============================================================================

function DriftTab() {
  const [data, setData] = useState<StrategyDriftInsight[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.fetchStrategyDriftInsights().then(setData).finally(() => setLoading(false));
  }, []);

  if (loading) return <Loading />;

  return (
    <div>
      <p className="mb-4 text-sm text-[var(--text-secondary)]">
        How consistent you are with your declared strategies over time. Dips indicate deviations from your plan.
      </p>

      {/* Consistency timeline */}
      <div className="mb-6 rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
        <h3 className="mb-3 text-sm font-medium text-[var(--text-secondary)]">Consistency Score Over Time</h3>
        <div className="flex items-end gap-1" style={{ height: 100 }}>
          {data.map((d) => {
            const color = d.consistency_score >= 80
              ? 'bg-[var(--accent-green)]'
              : d.consistency_score >= 60
              ? 'bg-[var(--accent-yellow)]'
              : 'bg-[var(--accent-red)]';
            return (
              <div key={d.date} className="flex flex-1 flex-col items-center gap-1">
                <div
                  className={`w-full rounded-t ${color}`}
                  style={{ height: `${d.consistency_score}%`, minHeight: 4 }}
                  title={`${d.date}: ${d.consistency_score}/100`}
                />
                <span className="text-[9px] text-[var(--text-secondary)]">{d.date.slice(8)}</span>
              </div>
            );
          })}
        </div>
        <div className="mt-1 flex justify-between text-[9px] text-[var(--text-secondary)]">
          <span>{data[0]?.date.slice(5)}</span>
          <span>{data[data.length - 1]?.date.slice(5)}</span>
        </div>
      </div>

      {/* Deviation details */}
      <DataTable
        columns={[
          { key: 'date', label: 'Date', render: (v: string) => v.slice(5) },
          { key: 'consistency_score', label: 'Score', render: (v: number) => <ScoreValue value={v} /> },
          {
            key: 'deviations',
            label: 'Deviations',
            render: (v: string[]) =>
              v.length > 0 ? (
                <div className="flex flex-wrap gap-1">
                  {v.map((d) => (
                    <span key={d} className="rounded bg-[var(--accent-red)]/10 px-1.5 py-0.5 text-[10px] text-[var(--accent-red)]">
                      {d.replace(/_/g, ' ')}
                    </span>
                  ))}
                </div>
              ) : (
                <span className="text-[var(--accent-green)] text-xs">On track</span>
              ),
          },
        ]}
        rows={data}
      />
    </div>
  );
}

// =============================================================================
// Shared display components
// =============================================================================

function Loading() {
  return <div className="py-8 text-center text-sm text-[var(--text-secondary)]">Loading...</div>;
}

function SummaryCard({
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

function ScoreValue({ value, label }: { value: number; label?: string }) {
  const color = value >= 70
    ? 'text-[var(--accent-green)]'
    : value >= 50
    ? 'text-[var(--accent-yellow)]'
    : 'text-[var(--accent-red)]';
  return <span className={`font-mono text-sm font-medium ${color}`}>{label ?? value}</span>;
}

function PnlValue({ value }: { value: number }) {
  const color = value >= 0 ? 'text-[var(--accent-green)]' : 'text-[var(--accent-red)]';
  return (
    <span className={`font-mono text-sm font-medium ${color}`}>
      {value > 0 ? '+' : ''}{value.toFixed(2)}%
    </span>
  );
}

function PctBar({ value, color, label }: { value: number; color: 'red' | 'blue'; label?: string }) {
  const barColor = color === 'red' ? 'bg-[var(--accent-red)]' : 'bg-[var(--accent-blue)]';
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-[var(--bg-primary)]">
        <div
          className={`h-full rounded-full ${barColor}`}
          style={{ width: `${Math.min(value, 100)}%` }}
        />
      </div>
      <span className="text-xs text-[var(--text-secondary)]">{label ?? `${Math.round(value)}%`}</span>
    </div>
  );
}

// Generic data table
interface Column<T> {
  key: string;
  label: string;
  render?: (value: any, row: T) => React.ReactNode;
}

function DataTable<T extends Record<string, any>>({ columns, rows }: { columns: Column<T>[]; rows: T[] }) {
  return (
    <div className="overflow-hidden rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)]">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[var(--border-color)] text-left text-xs font-medium text-[var(--text-secondary)]">
            {columns.map((col) => (
              <th key={col.key} className="px-4 py-2.5">{col.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-b border-[var(--border-color)] last:border-0">
              {columns.map((col) => (
                <td key={col.key} className="px-4 py-2.5">
                  {col.render ? col.render(row[col.key], row) : String(row[col.key] ?? '--')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
