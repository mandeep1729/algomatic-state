import { useEffect, useState, useMemo } from 'react';
import api, { fetchAggregatePnlTimeseries } from '../../api';
import type { DailyPnlPoint } from '../../api';
import type { CampaignSummary, InsightsSummary, TimingInsight } from '../../types';
import { StatCard } from '../../components/ui/StatCard';
import { Section } from '../../components/ui/Section';
import { EquityCurveChart } from '../../components/charts/EquityCurveChart';
import { DrawdownChart } from '../../components/charts/DrawdownChart';
import { RollingSharpeChart } from '../../components/charts/RollingSharpeChart';
import { ReturnDistributionChart } from '../../components/charts/ReturnDistributionChart';
import { HoldingReturnScatterChart } from '../../components/charts/HoldingReturnScatterChart';
import type { ScatterPoint } from '../../components/charts/HoldingReturnScatterChart';
import { TimeOfDayHeatmapChart } from '../../components/charts/TimeOfDayHeatmapChart';
import { computeExpectancy, computeHoldingMinutes, computeDrawdown } from '../../utils/dashboardMetrics';

export default function Dashboard() {
  const [pnlData, setPnlData] = useState<DailyPnlPoint[]>([]);
  const [campaigns, setCampaigns] = useState<CampaignSummary[]>([]);
  const [insights, setInsights] = useState<InsightsSummary | null>(null);
  const [timing, setTiming] = useState<TimingInsight[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [pnl, camps, ins, tim] = await Promise.all([
          fetchAggregatePnlTimeseries().catch(() => [] as DailyPnlPoint[]),
          api.fetchCampaigns().catch(() => [] as CampaignSummary[]),
          api.fetchInsightsSummary().catch(() => null),
          api.fetchTimingInsights().catch(() => [] as TimingInsight[]),
        ]);
        setPnlData(pnl);
        setCampaigns(camps);
        setInsights(ins);
        setTiming(tim);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  // Derived metrics
  const closedCampaigns = useMemo(
    () => campaigns.filter((c) => c.status === 'closed' && c.pnlRealized != null),
    [campaigns],
  );

  const returns = useMemo(
    () => closedCampaigns.map((c) => c.pnlRealized!),
    [closedCampaigns],
  );

  const totalPnl = useMemo(
    () => pnlData.length > 0 ? pnlData[pnlData.length - 1].cumulativePnl : 0,
    [pnlData],
  );

  const maxDrawdown = useMemo(() => {
    if (pnlData.length === 0) return 0;
    const dd = computeDrawdown(pnlData.map((p) => p.cumulativePnl));
    return Math.min(...dd);
  }, [pnlData]);

  const expectancy = useMemo(() => computeExpectancy(returns), [returns]);

  const avgWin = useMemo(() => {
    const wins = returns.filter((r) => r > 0);
    return wins.length > 0 ? wins.reduce((a, b) => a + b, 0) / wins.length : 0;
  }, [returns]);

  const avgLoss = useMemo(() => {
    const losses = returns.filter((r) => r <= 0);
    return losses.length > 0 ? Math.abs(losses.reduce((a, b) => a + b, 0) / losses.length) : 0;
  }, [returns]);

  const profitFactor = useMemo(() => {
    const totalWins = returns.filter((r) => r > 0).reduce((a, b) => a + b, 0);
    const totalLosses = Math.abs(returns.filter((r) => r <= 0).reduce((a, b) => a + b, 0));
    return totalLosses > 0 ? totalWins / totalLosses : totalWins > 0 ? Infinity : 0;
  }, [returns]);

  const scatterPoints: ScatterPoint[] = useMemo(
    () => closedCampaigns
      .filter((c) => c.closedAt)
      .map((c) => ({
        holdingMinutes: computeHoldingMinutes(c.openedAt, c.closedAt!),
        returnDollars: c.pnlRealized!,
        symbol: c.symbol,
      })),
    [closedCampaigns],
  );

  // Chart data
  const timestamps = useMemo(() => pnlData.map((p) => p.date), [pnlData]);
  const cumulativePnl = useMemo(() => pnlData.map((p) => p.cumulativePnl), [pnlData]);
  const dailyPnl = useMemo(() => pnlData.map((p) => p.realizedPnl), [pnlData]);

  // Sharpe from overall data
  const overallSharpe = useMemo(() => {
    if (dailyPnl.length < 2) return null;
    const mean = dailyPnl.reduce((a, b) => a + b, 0) / dailyPnl.length;
    const variance = dailyPnl.reduce((a, b) => a + (b - mean) ** 2, 0) / dailyPnl.length;
    const std = Math.sqrt(variance);
    return std === 0 ? (mean >= 0 ? Infinity : -Infinity) : (mean / std) * Math.sqrt(252);
  }, [dailyPnl]);

  if (loading) {
    return <div className="p-8 text-[var(--text-secondary)]">Loading dashboard...</div>;
  }

  const winRate = insights?.win_rate;
  const totalTrades = insights?.total_trades ?? closedCampaigns.length;

  return (
    <div className="p-6">
      <h1 className="mb-6 text-2xl font-semibold">Dashboard</h1>

      {/* Key Metrics Strip */}
      <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5 xl:grid-cols-9">
        <StatCard
          label="Total P&L"
          value={`${totalPnl >= 0 ? '+' : ''}$${totalPnl.toFixed(2)}`}
          accent={totalPnl >= 0 ? 'green' : 'red'}
        />
        <StatCard
          label="Total Trades"
          value={totalTrades}
        />
        <StatCard
          label="Win Rate"
          value={winRate != null ? `${(winRate * 100).toFixed(0)}%` : '--'}
          accent={winRate != null ? (winRate >= 0.5 ? 'green' : winRate >= 0.4 ? 'yellow' : 'red') : undefined}
        />
        <StatCard
          label="Avg R:R"
          value={insights?.avg_risk_reward?.toFixed(2) ?? '--'}
          accent={insights?.avg_risk_reward != null ? (insights.avg_risk_reward >= 1.5 ? 'green' : 'yellow') : undefined}
        />
        <StatCard
          label="Sharpe"
          value={overallSharpe != null && isFinite(overallSharpe) ? overallSharpe.toFixed(2) : '--'}
          accent={overallSharpe != null && isFinite(overallSharpe) ? (overallSharpe >= 1 ? 'green' : overallSharpe >= 0.5 ? 'yellow' : 'red') : undefined}
        />
        <StatCard
          label="Max Drawdown"
          value={maxDrawdown !== 0 ? `$${maxDrawdown.toFixed(2)}` : '--'}
          accent={maxDrawdown < 0 ? 'red' : undefined}
        />
        <StatCard
          label="Profit Factor"
          value={profitFactor > 0 && isFinite(profitFactor) ? profitFactor.toFixed(2) : '--'}
          accent={profitFactor >= 1.5 ? 'green' : profitFactor >= 1 ? 'yellow' : 'red'}
        />
        <StatCard
          label="Expectancy"
          value={expectancy != null ? `$${expectancy.toFixed(2)}` : '--'}
          accent={expectancy != null ? (expectancy > 0 ? 'green' : 'red') : undefined}
        />
        <StatCard
          label="Avg Win / Loss"
          value={avgWin > 0 || avgLoss > 0 ? `$${avgWin.toFixed(0)} / $${avgLoss.toFixed(0)}` : '--'}
        />
      </div>

      {/* Row 1: Equity Curve + Performance Summary */}
      <div className="mb-6 grid gap-6 lg:grid-cols-[3fr_2fr]">
        <Section title="Equity Curve">
          <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-3">
            {pnlData.length > 0 ? (
              <EquityCurveChart timestamps={timestamps} cumulativePnl={cumulativePnl} height={280} />
            ) : (
              <EmptyChart message="No P&L data yet. Trade data will appear here once campaigns are tracked." />
            )}
          </div>
        </Section>

        <Section title="Performance Summary">
          <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
            <div className="space-y-3">
              <SummaryRow label="Total Realized P&L" value={`${totalPnl >= 0 ? '+' : ''}$${totalPnl.toFixed(2)}`} color={totalPnl >= 0 ? 'green' : 'red'} />
              <SummaryRow label="Closed Campaigns" value={String(closedCampaigns.length)} />
              <SummaryRow label="Open Campaigns" value={String(campaigns.filter((c) => c.status === 'open').length)} />
              <SummaryRow label="Win Rate" value={winRate != null ? `${(winRate * 100).toFixed(1)}%` : '--'} color={winRate != null ? (winRate >= 0.5 ? 'green' : 'red') : undefined} />
              <SummaryRow label="Average Win" value={avgWin > 0 ? `+$${avgWin.toFixed(2)}` : '--'} color={avgWin > 0 ? 'green' : undefined} />
              <SummaryRow label="Average Loss" value={avgLoss > 0 ? `-$${avgLoss.toFixed(2)}` : '--'} color={avgLoss > 0 ? 'red' : undefined} />
              <SummaryRow label="Profit Factor" value={profitFactor > 0 && isFinite(profitFactor) ? profitFactor.toFixed(2) : '--'} />
              <SummaryRow label="Expectancy" value={expectancy != null ? `$${expectancy.toFixed(2)}` : '--'} color={expectancy != null ? (expectancy > 0 ? 'green' : 'red') : undefined} />
              <SummaryRow label="Emotional Stability" value="--" />
              <SummaryRow label="Entry Quality" value="--" />
            </div>
          </div>
        </Section>
      </div>

      {/* Row 2: Drawdown + Rolling Sharpe */}
      <div className="mb-6 grid gap-6 lg:grid-cols-2">
        <Section title="Drawdown">
          <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-3">
            {pnlData.length > 0 ? (
              <DrawdownChart timestamps={timestamps} cumulativePnl={cumulativePnl} height={220} />
            ) : (
              <EmptyChart message="Drawdown chart requires P&L data." height={220} />
            )}
          </div>
        </Section>

        <Section title="Rolling Sharpe (20-day)">
          <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-3">
            {dailyPnl.length >= 20 ? (
              <RollingSharpeChart dailyPnl={dailyPnl} dates={timestamps} height={220} />
            ) : (
              <EmptyChart message="Need at least 20 trading days for rolling Sharpe." height={220} />
            )}
          </div>
        </Section>
      </div>

      {/* Row 3: Return Distribution + Holding Period Scatter */}
      <div className="mb-6 grid gap-6 lg:grid-cols-2">
        <Section title="Return Distribution">
          <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-3">
            {returns.length > 0 ? (
              <ReturnDistributionChart returns={returns} height={220} />
            ) : (
              <EmptyChart message="No closed campaigns to show return distribution." height={220} />
            )}
          </div>
        </Section>

        <Section title="Holding Period vs Return">
          <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-3">
            {scatterPoints.length > 0 ? (
              <HoldingReturnScatterChart points={scatterPoints} height={220} />
            ) : (
              <EmptyChart message="No closed campaigns with holding period data." height={220} />
            )}
          </div>
        </Section>
      </div>

      {/* Row 4: Time-of-Day Heatmap */}
      <Section title="Trading Activity by Hour">
        <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-3">
          {timing.length > 0 ? (
            <TimeOfDayHeatmapChart timingData={timing} height={160} />
          ) : (
            <EmptyChart message="No timing data available yet." height={160} />
          )}
        </div>
      </Section>
    </div>
  );
}

function SummaryRow({ label, value, color }: { label: string; value: string; color?: 'green' | 'red' }) {
  const colorClass = color === 'green'
    ? 'text-[var(--accent-green)]'
    : color === 'red'
      ? 'text-[var(--accent-red)]'
      : 'text-[var(--text-primary)]';

  return (
    <div className="flex items-center justify-between border-b border-[var(--border-color)] pb-2 last:border-0 last:pb-0">
      <span className="text-xs text-[var(--text-secondary)]">{label}</span>
      <span className={`text-sm font-medium font-mono ${colorClass}`}>{value}</span>
    </div>
  );
}

function EmptyChart({ message, height = 280 }: { message: string; height?: number }) {
  return (
    <div
      className="flex items-center justify-center text-sm text-[var(--text-secondary)]"
      style={{ height: `${height}px` }}
    >
      {message}
    </div>
  );
}
