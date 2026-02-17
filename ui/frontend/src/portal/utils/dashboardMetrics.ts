/**
 * Pure computation functions for the Dashboard page.
 * All functions are stateless and can be used in useMemo.
 */

/** Compute drawdown series from cumulative P&L values. Always <= 0. */
export function computeDrawdown(cumulativePnl: number[]): number[] {
  const drawdown: number[] = [];
  let peak = -Infinity;
  for (const pnl of cumulativePnl) {
    if (pnl > peak) peak = pnl;
    drawdown.push(pnl - peak);
  }
  return drawdown;
}

/**
 * Compute rolling Sharpe ratio from daily P&L values.
 * Uses a `window`-day rolling window and annualizes by sqrt(252).
 * Returns null for points with insufficient data.
 */
export function computeRollingSharpe(
  dailyPnl: number[],
  window: number = 20,
): (number | null)[] {
  const result: (number | null)[] = [];
  for (let i = 0; i < dailyPnl.length; i++) {
    if (i < window - 1) {
      result.push(null);
      continue;
    }
    const slice = dailyPnl.slice(i - window + 1, i + 1);
    const mean = slice.reduce((a, b) => a + b, 0) / slice.length;
    const variance = slice.reduce((a, b) => a + (b - mean) ** 2, 0) / slice.length;
    const std = Math.sqrt(variance);
    if (std === 0) {
      result.push(mean >= 0 ? Infinity : -Infinity);
    } else {
      result.push((mean / std) * Math.sqrt(252));
    }
  }
  return result;
}

/**
 * Compute expectancy: winRate * avgWin - (1 - winRate) * avgLoss.
 * Returns null if no trades.
 */
export function computeExpectancy(returns: number[]): number | null {
  if (returns.length === 0) return null;
  const wins = returns.filter((r) => r > 0);
  const losses = returns.filter((r) => r <= 0);
  const winRate = wins.length / returns.length;
  const avgWin = wins.length > 0 ? wins.reduce((a, b) => a + b, 0) / wins.length : 0;
  const avgLoss = losses.length > 0 ? Math.abs(losses.reduce((a, b) => a + b, 0) / losses.length) : 0;
  return winRate * avgWin - (1 - winRate) * avgLoss;
}

/** Build histogram bins from a set of numeric values. */
export function buildHistogramBins(
  values: number[],
  binCount: number = 20,
): { min: number; max: number; count: number; label: string }[] {
  if (values.length === 0) return [];
  const min = Math.min(...values);
  const max = Math.max(...values);
  if (min === max) {
    return [{ min, max, count: values.length, label: `${min.toFixed(0)}` }];
  }
  const binWidth = (max - min) / binCount;
  const bins = Array.from({ length: binCount }, (_, i) => ({
    min: min + i * binWidth,
    max: min + (i + 1) * binWidth,
    count: 0,
    label: `${(min + (i + 0.5) * binWidth).toFixed(0)}`,
  }));
  for (const v of values) {
    let idx = Math.floor((v - min) / binWidth);
    if (idx >= binCount) idx = binCount - 1;
    bins[idx].count++;
  }
  return bins;
}

/** Compute holding period in minutes from ISO timestamps. */
export function computeHoldingMinutes(openedAt: string, closedAt: string): number {
  return (new Date(closedAt).getTime() - new Date(openedAt).getTime()) / 60_000;
}

/** Format minutes into human readable duration. */
export function formatDuration(minutes: number): string {
  if (minutes < 60) return `${Math.round(minutes)}m`;
  if (minutes < 1440) return `${(minutes / 60).toFixed(1)}h`;
  return `${(minutes / 1440).toFixed(1)}d`;
}
