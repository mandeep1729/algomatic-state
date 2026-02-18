/**
 * Subset metrics computation for the Investigate page.
 *
 * Given a filtered set of campaigns, compute aggregate performance metrics.
 */

import type { CampaignSummary } from '../types';
import { computeDrawdown, computeExpectancy } from './dashboardMetrics';

export type ConfidenceLevel = 'low' | 'medium' | 'higher';

export interface SubsetMetrics {
  totalPnl: number;
  winRate: number | null;
  avgPnl: number | null;
  maxDrawdown: number;
  tradeCount: number;
  expectancy: number | null;
  confidence: ConfidenceLevel;
}

/** Determine confidence level from sample size. */
export function confidenceFromCount(n: number): ConfidenceLevel {
  if (n < 30) return 'low';
  if (n < 100) return 'medium';
  return 'higher';
}

/** Compute metrics for a set of campaigns. */
export function computeSubsetMetrics(campaigns: CampaignSummary[]): SubsetMetrics {
  const closed = campaigns.filter((c) => c.status === 'closed' && c.pnlRealized != null);
  const returns = closed.map((c) => c.pnlRealized!);

  const totalPnl = returns.reduce((a, b) => a + b, 0);
  const tradeCount = closed.length;
  const winRate = tradeCount > 0
    ? returns.filter((r) => r > 0).length / tradeCount
    : null;
  const avgPnl = tradeCount > 0 ? totalPnl / tradeCount : null;

  // Approximate drawdown from sorted cumulative sum
  const sorted = [...closed].sort(
    (a, b) => new Date(a.openedAt).getTime() - new Date(b.openedAt).getTime(),
  );
  let cumulative = 0;
  const cumSeries = sorted.map((c) => {
    cumulative += c.pnlRealized!;
    return cumulative;
  });
  const dd = computeDrawdown(cumSeries);
  const maxDrawdown = dd.length > 0 ? Math.min(...dd) : 0;

  const expectancy = computeExpectancy(returns);
  const confidence = confidenceFromCount(tradeCount);

  return { totalPnl, winRate, avgPnl, maxDrawdown, tradeCount, expectancy, confidence };
}
