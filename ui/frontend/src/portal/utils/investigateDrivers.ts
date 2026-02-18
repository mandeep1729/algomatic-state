/**
 * Driver computation for the WHY panel.
 *
 * Groups campaigns by dimension (symbol, strategy, flag, direction),
 * computes impact metrics, and ranks by absolute PnL contribution.
 */

import type { CampaignSummary } from '../types';
import { confidenceFromCount, type ConfidenceLevel } from './investigateMetrics';

export interface Driver {
  dimension: 'symbol' | 'strategy' | 'flag' | 'direction';
  key: string;
  totalPnl: number;
  tradeCount: number;
  winRate: number;
  avgPnl: number;
  confidence: ConfidenceLevel;
  explanation: string;
}

export interface Drivers {
  negative: Driver[];
  positive: Driver[];
}

interface GroupAccumulator {
  totalPnl: number;
  wins: number;
  count: number;
}

/** Group campaigns by a dimension, accumulating PnL stats. */
function groupBy(
  campaigns: CampaignSummary[],
  keyExtractor: (c: CampaignSummary) => string[],
): Map<string, GroupAccumulator> {
  const groups = new Map<string, GroupAccumulator>();

  for (const c of campaigns) {
    if (c.status !== 'closed' || c.pnlRealized == null) continue;
    const keys = keyExtractor(c);
    for (const key of keys) {
      const acc = groups.get(key) ?? { totalPnl: 0, wins: 0, count: 0 };
      acc.totalPnl += c.pnlRealized;
      if (c.pnlRealized > 0) acc.wins++;
      acc.count++;
      groups.set(key, acc);
    }
  }

  return groups;
}

/** Convert a group map into Driver objects. */
function toDrivers(
  groups: Map<string, GroupAccumulator>,
  dimension: Driver['dimension'],
): Driver[] {
  return Array.from(groups.entries()).map(([key, acc]) => {
    const winRate = acc.count > 0 ? acc.wins / acc.count : 0;
    const avgPnl = acc.count > 0 ? acc.totalPnl / acc.count : 0;
    const confidence = confidenceFromCount(acc.count);

    const sign = acc.totalPnl >= 0 ? 'gained' : 'lost';
    const pnlStr = `$${Math.abs(acc.totalPnl).toFixed(0)}`;
    const wrStr = `${(winRate * 100).toFixed(0)}% win rate`;

    const explanation =
      dimension === 'symbol'
        ? `${key} ${sign} ${pnlStr} across ${acc.count} trade${acc.count !== 1 ? 's' : ''} (${wrStr})`
        : dimension === 'strategy'
          ? `Your '${key}' strategy ${sign} ${pnlStr} across ${acc.count} trade${acc.count !== 1 ? 's' : ''} (${wrStr})`
          : dimension === 'flag'
            ? `Trades flagged '${key}' ${sign} ${pnlStr} across ${acc.count} occurrence${acc.count !== 1 ? 's' : ''}`
            : `${key} trades ${sign} ${pnlStr} across ${acc.count} trade${acc.count !== 1 ? 's' : ''} (${wrStr})`;

    return {
      dimension,
      key,
      totalPnl: acc.totalPnl,
      tradeCount: acc.count,
      winRate,
      avgPnl,
      confidence,
      explanation,
    };
  });
}

/** Compute top negative and positive drivers from a set of campaigns. */
export function computeDrivers(campaigns: CampaignSummary[], topN: number = 5): Drivers {
  const allDrivers: Driver[] = [];

  // Group by symbol
  const bySymbol = groupBy(campaigns, (c) => [c.symbol]);
  allDrivers.push(...toDrivers(bySymbol, 'symbol'));

  // Group by strategy
  const byStrategy = groupBy(campaigns, (c) =>
    c.strategies.length > 0 ? c.strategies : ['(none)'],
  );
  allDrivers.push(...toDrivers(byStrategy, 'strategy'));

  // Group by flag
  const byFlag = groupBy(campaigns, (c) =>
    c.keyFlags.length > 0 ? c.keyFlags : [],
  );
  allDrivers.push(...toDrivers(byFlag, 'flag'));

  // Group by direction
  const byDirection = groupBy(campaigns, (c) => [c.direction]);
  allDrivers.push(...toDrivers(byDirection, 'direction'));

  // Sort by absolute impact
  const sorted = [...allDrivers].sort((a, b) => Math.abs(b.totalPnl) - Math.abs(a.totalPnl));

  const negative = sorted.filter((d) => d.totalPnl < 0).slice(0, topN);
  const positive = sorted.filter((d) => d.totalPnl > 0).slice(0, topN);

  return { negative, positive };
}
