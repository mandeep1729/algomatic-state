/**
 * BehaviorLabTab — flag frequency chart, timing heatmap, behavioral insights.
 */

import { useMemo } from 'react';
import { useInvestigate } from '../../context/InvestigateContext';
import { Section } from '../ui/Section';
import { FlagFrequencyChart, type FlagData } from '../charts/FlagFrequencyChart';
import { TimeOfDayHeatmapChart } from '../charts/TimeOfDayHeatmapChart';
import { ChartHelp } from './ChartHelp';
import { AlertTriangle, TrendingUp, Minus } from 'lucide-react';

export function BehaviorLabTab() {
  const { subset, timingData, behavioralData, addFilter } = useInvestigate();

  // Build flag frequency data from subset campaigns
  const flagData = useMemo((): FlagData[] => {
    const map = new Map<string, { count: number; totalPnl: number }>();

    for (const c of subset) {
      if (c.keyFlags.length === 0) continue;
      const pnl = c.pnlRealized ?? 0;
      for (const flag of c.keyFlags) {
        const acc = map.get(flag) ?? { count: 0, totalPnl: 0 };
        acc.count++;
        acc.totalPnl += pnl;
        map.set(flag, acc);
      }
    }

    return Array.from(map.entries()).map(([flag, { count, totalPnl }]) => ({
      flag,
      count,
      avgPnl: count > 0 ? totalPnl / count : 0,
    }));
  }, [subset]);

  function handleFlagClick(flag: string) {
    addFilter('flag', 'eq', flag, `Flag: ${flag}`, 'chart-click');
  }

  return (
    <div className="space-y-6 pt-4">
      {/* Flag Frequency */}
      <Section title="Flag Frequency">
        <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-3">
          {flagData.length > 0 ? (
            <FlagFrequencyChart
              data={flagData}
              height={Math.max(200, flagData.length * 30 + 60)}
              onBarClick={handleFlagClick}
            />
          ) : (
            <div className="flex h-[200px] items-center justify-center text-sm text-[var(--text-secondary)]">
              No flags found on campaigns. Flags will appear here once your evaluator has flagged trades.
            </div>
          )}
        </div>
        <ChartHelp
          what="How often each behavioral flag appears in your trades. Bar color shows the average P&L impact."
          how="Frequent red flags are patterns to break. Green flags are behaviors worth reinforcing."
          click="Click a bar to filter campaigns by that flag and investigate the trades behind it."
        />
      </Section>

      {/* Trading Activity by Hour */}
      <Section title="Trading Activity by Hour">
        <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-3">
          {timingData.length > 0 ? (
            <TimeOfDayHeatmapChart timingData={timingData} height={160} />
          ) : (
            <div className="flex h-[160px] items-center justify-center text-sm text-[var(--text-secondary)]">
              No timing data available yet. This will populate as you accumulate more trades.
            </div>
          )}
        </div>
        <ChartHelp
          what="When you trade throughout the day and how quality varies by hour."
          how="Identify high-risk trading windows (e.g., first/last 30 min) and times when your performance is weakest."
          click="Use this to inform rules about when to trade and when to sit out."
        />
      </Section>

      {/* Behavioral Insights */}
      <Section title="Behavioral Insights">
        {behavioralData.length > 0 ? (
          <div className="space-y-2">
            {behavioralData.map((insight) => {
              const isPositive = insight.avg_outcome_pct != null && insight.avg_outcome_pct > 0;
              const isNeutral = insight.avg_outcome_pct == null;

              return (
                <div
                  key={insight.signal}
                  className="flex items-start gap-3 rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-3"
                >
                  <div className="mt-0.5">
                    {isNeutral ? (
                      <Minus size={14} className="text-[var(--text-secondary)]" />
                    ) : isPositive ? (
                      <TrendingUp size={14} className="text-[var(--accent-green)]" />
                    ) : (
                      <AlertTriangle size={14} className="text-[var(--accent-red)]" />
                    )}
                  </div>
                  <div className="flex-1">
                    <div className="text-xs font-medium text-[var(--text-primary)]">{insight.signal}</div>
                    <div className="mt-0.5 text-[10px] text-[var(--text-secondary)]">
                      {insight.occurrence_count} occurrence{insight.occurrence_count !== 1 ? 's' : ''}
                      {' '} ({(insight.pct_of_trades * 100).toFixed(0)}% of trades)
                      {insight.avg_outcome_pct != null && (
                        <span className={isPositive ? 'text-[var(--accent-green)]' : 'text-[var(--accent-red)]'}>
                          {' '} avg outcome: {insight.avg_outcome_pct >= 0 ? '+' : ''}{(insight.avg_outcome_pct * 100).toFixed(1)}%
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-6 text-center text-sm text-[var(--text-secondary)]">
            Behavioral insights will appear here as you log more decision contexts and trade data.
          </div>
        )}
      </Section>
    </div>
  );
}
