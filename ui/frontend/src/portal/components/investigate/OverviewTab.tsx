/**
 * OverviewTab — equity curve, drawdown, driver summary cards.
 */

import { useMemo } from 'react';
import { useInvestigate } from '../../context/InvestigateContext';
import { Section } from '../ui/Section';
import { EquityCurveChart } from '../charts/EquityCurveChart';
import { DrawdownChart } from '../charts/DrawdownChart';
import { ChartHelp } from './ChartHelp';
import type { CampaignSummary } from '../../types';

/** Build a synthetic cumulative PnL series from campaigns sorted by close date. */
function buildCampaignEquityCurve(campaigns: CampaignSummary[]) {
  const closed = campaigns
    .filter((c) => c.status === 'closed' && c.pnlRealized != null && c.closedAt)
    .sort((a, b) => new Date(a.closedAt!).getTime() - new Date(b.closedAt!).getTime());

  let cum = 0;
  const timestamps: string[] = [];
  const cumulativePnl: number[] = [];

  for (const c of closed) {
    cum += c.pnlRealized!;
    const date = new Date(c.closedAt!).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
    });
    timestamps.push(date);
    cumulativePnl.push(cum);
  }

  return { timestamps, cumulativePnl };
}

function EmptyChart({ message, height = 260 }: { message: string; height?: number }) {
  return (
    <div
      className="flex items-center justify-center text-sm text-[var(--text-secondary)]"
      style={{ height: `${height}px` }}
    >
      {message}
    </div>
  );
}

export function OverviewTab() {
  const { pnlTimeseries, subset, drivers, compareEnabled, filters } = useInvestigate();
  const isFiltered = filters.length > 0;

  // For unfiltered view, use real PnL timeseries; for filtered, build from campaigns
  const mainCurve = useMemo(() => {
    if (isFiltered) {
      return buildCampaignEquityCurve(subset);
    }
    return {
      timestamps: pnlTimeseries.map((p) => p.date),
      cumulativePnl: pnlTimeseries.map((p) => p.cumulativePnl),
    };
  }, [isFiltered, subset, pnlTimeseries]);

  // Top drivers for summary cards
  const topNegative = drivers.negative.slice(0, 3);
  const topPositive = drivers.positive.slice(0, 3);

  return (
    <div className="space-y-6 pt-4">
      {/* Equity Curve */}
      <Section title={isFiltered ? 'Subset Equity Curve' : 'Equity Curve'}>
        <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-3">
          {mainCurve.timestamps.length > 0 ? (
            <EquityCurveChart
              timestamps={mainCurve.timestamps}
              cumulativePnl={mainCurve.cumulativePnl}
              height={280}
            />
          ) : (
            <EmptyChart message="No trade data for equity curve. Close some campaigns to see this chart." />
          )}
        </div>
        <ChartHelp
          what="Cumulative P&L over time. Shows how your capital has grown or shrunk."
          how="Look for consistent upward slope (good) vs steep drops (drawdowns to investigate)."
          click="Use filters to isolate specific tickers or strategies and see their individual contribution."
        />
      </Section>

      {/* Drawdown */}
      <Section title="Drawdown">
        <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-3">
          {mainCurve.timestamps.length > 0 ? (
            <DrawdownChart
              timestamps={mainCurve.timestamps}
              cumulativePnl={mainCurve.cumulativePnl}
              height={200}
            />
          ) : (
            <EmptyChart message="Drawdown chart requires P&L data." height={200} />
          )}
        </div>
        <ChartHelp
          what="How far below peak equity you've fallen at each point. Always negative or zero."
          how="Deep drawdowns reveal when things went wrong. Filter by that time period to see which trades caused it."
          click="Filter by date range to isolate drawdown periods and investigate the trades behind them."
        />
      </Section>

      {/* Driver Summary Cards */}
      {(topNegative.length > 0 || topPositive.length > 0) && (
        <Section title="Key Drivers">
          <div className="grid gap-4 md:grid-cols-2">
            {/* Biggest losers */}
            {topNegative.length > 0 && (
              <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
                <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-[var(--accent-red)]">
                  Biggest Drags
                </h3>
                <div className="space-y-2">
                  {topNegative.map((d) => (
                    <div key={`${d.dimension}-${d.key}`} className="flex items-center justify-between border-b border-[var(--border-color)] pb-2 last:border-0 last:pb-0">
                      <div>
                        <span className="text-xs font-medium text-[var(--text-primary)]">{d.key}</span>
                        <span className="ml-1.5 text-[10px] text-[var(--text-secondary)]">{d.dimension}</span>
                      </div>
                      <span className="text-sm font-mono font-semibold text-[var(--accent-red)]">
                        ${d.totalPnl.toFixed(0)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Biggest winners */}
            {topPositive.length > 0 && (
              <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
                <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-[var(--accent-green)]">
                  Biggest Contributors
                </h3>
                <div className="space-y-2">
                  {topPositive.map((d) => (
                    <div key={`${d.dimension}-${d.key}`} className="flex items-center justify-between border-b border-[var(--border-color)] pb-2 last:border-0 last:pb-0">
                      <div>
                        <span className="text-xs font-medium text-[var(--text-primary)]">{d.key}</span>
                        <span className="ml-1.5 text-[10px] text-[var(--text-secondary)]">{d.dimension}</span>
                      </div>
                      <span className="text-sm font-mono font-semibold text-[var(--accent-green)]">
                        +${d.totalPnl.toFixed(0)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </Section>
      )}

      {/* Compare mode note */}
      {compareEnabled && isFiltered && (
        <div className="rounded-md border border-[var(--accent-purple)]/30 bg-[var(--accent-purple)]/5 p-3 text-xs text-[var(--accent-purple)]">
          Compare mode is active. The equity curve shows your filtered subset.
          Check the metrics strip above to see how subset performance differs from all trades.
        </div>
      )}
    </div>
  );
}
