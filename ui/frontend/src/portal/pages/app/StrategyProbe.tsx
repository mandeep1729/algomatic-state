import { useEffect, useState, useCallback, useMemo } from 'react';
import { fetchStrategyProbe } from '../../api';
import type { StrategyProbeResponse, WeekPerformance, StrategyRanking } from '../../api';

/**
 * Compute a default start date 3 months before today (YYYY-MM-DD).
 */
function defaultStartDate(): string {
  const d = new Date();
  d.setMonth(d.getMonth() - 3);
  return d.toISOString().split('T')[0];
}

function todayStr(): string {
  return new Date().toISOString().split('T')[0];
}

// ---------------------------------------------------------------------------
// Strategy color system
// ---------------------------------------------------------------------------

/** Known category-to-hue mapping. */
const CATEGORY_HUE_MAP: Record<string, number> = {
  trend: 220,
  mean_reversion: 280,
  breakout: 40,
  momentum: 100,
  volatility: 0,
};

/** Human-readable labels for known categories. */
const CATEGORY_LABELS: Record<string, string> = {
  trend: 'Trend',
  mean_reversion: 'Mean Reversion',
  breakout: 'Breakout',
  momentum: 'Momentum',
  volatility: 'Volatility',
};

/**
 * Simple string hash to assign a stable hue for unknown categories.
 * Returns a value in [0, 360).
 */
function stringToHue(str: string): number {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = str.charCodeAt(i) + ((hash << 5) - hash);
    hash = hash & hash; // Convert to 32-bit int
  }
  return ((hash % 360) + 360) % 360;
}

/**
 * Get the base hue for a strategy category.
 */
function getCategoryHue(category: string): number {
  const normalized = category.toLowerCase().replace(/\s+/g, '_');
  return CATEGORY_HUE_MAP[normalized] ?? stringToHue(normalized);
}

interface StrategyColors {
  /** Background color with transparency for the row. */
  bg: string;
  /** Solid accent color for the left border. */
  border: string;
  /** Text color that meets contrast requirements against the background. */
  text: string;
}

/**
 * Compute HSL-based colors for a strategy row.
 *
 * - Maps category to a base hue.
 * - Normalizes weightedAvgPnl within the week's min/max range.
 * - Better performers get saturated, darker colors; worse get desaturated, lighter.
 */
function getStrategyColor(
  category: string,
  weightedAvgPnl: number,
  weekMinPnl: number,
  weekMaxPnl: number,
): StrategyColors {
  const hue = getCategoryHue(category);

  // Normalize PnL to [0, 1] where 1 = best performer
  const range = weekMaxPnl - weekMinPnl;
  const normalized = range === 0 ? 0.5 : (weightedAvgPnl - weekMinPnl) / range;

  // Saturation: 50% (worst) to 100% (best)
  const saturation = 50 + normalized * 50;
  // Lightness: 70% (worst, light/muted) to 50% (best, vivid)
  const lightness = 70 - normalized * 20;

  return {
    bg: `hsla(${hue}, ${saturation}%, ${lightness}%, 0.15)`,
    border: `hsl(${hue}, 100%, 45%)`,
    text: lightness > 60 ? '#333333' : '#f0f0f0',
  };
}

/**
 * Compute the min and max weighted_avg_pnl across strategies in a week.
 */
function weekPnlRange(strategies: StrategyRanking[]): { min: number; max: number } {
  if (strategies.length === 0) return { min: 0, max: 0 };
  let min = Infinity;
  let max = -Infinity;
  for (const s of strategies) {
    if (s.weighted_avg_pnl < min) min = s.weighted_avg_pnl;
    if (s.weighted_avg_pnl > max) max = s.weighted_avg_pnl;
  }
  return { min, max };
}

/**
 * Collect all unique categories present in the data.
 */
function collectCategories(weeks: WeekPerformance[]): string[] {
  const seen = new Set<string>();
  for (const week of weeks) {
    for (const s of week.strategies) {
      seen.add(s.category.toLowerCase().replace(/\s+/g, '_'));
    }
  }
  // Sort known categories first (in defined order), then unknowns alphabetically
  const knownOrder = Object.keys(CATEGORY_HUE_MAP);
  const known: string[] = [];
  const unknown: string[] = [];
  for (const cat of seen) {
    if (knownOrder.includes(cat)) {
      known.push(cat);
    } else {
      unknown.push(cat);
    }
  }
  known.sort((a, b) => knownOrder.indexOf(a) - knownOrder.indexOf(b));
  unknown.sort();
  return [...known, ...unknown];
}

/**
 * Return a text color class based on PnL value.
 */
function pnlTextClass(pnl: number): string {
  if (pnl > 0) return 'text-green-400';
  if (pnl < 0) return 'text-red-400';
  return 'text-[var(--text-secondary)]';
}

/**
 * Format a dollar value with sign.
 */
function formatDollars(val: number): string {
  const sign = val >= 0 ? '+' : '';
  return `${sign}$${val.toFixed(2)}`;
}

// ---------------------------------------------------------------------------
// Components
// ---------------------------------------------------------------------------

function WeekCard({ week }: { week: WeekPerformance }) {
  const { min, max } = useMemo(() => weekPnlRange(week.strategies), [week.strategies]);

  return (
    <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-primary)] p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-[var(--text-primary)]">
          {week.week_start} &mdash; {week.week_end}
        </h3>
        <span className="text-xs text-[var(--text-secondary)]">
          {week.strategies.length} {week.strategies.length === 1 ? 'strategy' : 'strategies'}
        </span>
      </div>

      <div className="space-y-1.5">
        {week.strategies.map((s, idx) => (
          <StrategyRow
            key={`${s.category}-${s.theme}-${idx}`}
            strategy={s}
            weekMinPnl={min}
            weekMaxPnl={max}
          />
        ))}
      </div>
    </div>
  );
}

interface StrategyRowProps {
  strategy: StrategyRanking;
  weekMinPnl: number;
  weekMaxPnl: number;
}

function StrategyRow({ strategy, weekMinPnl, weekMaxPnl }: StrategyRowProps) {
  const colors = useMemo(
    () => getStrategyColor(strategy.category, strategy.weighted_avg_pnl, weekMinPnl, weekMaxPnl),
    [strategy.category, strategy.weighted_avg_pnl, weekMinPnl, weekMaxPnl],
  );

  const tooltipText = [
    `Category: ${strategy.category}`,
    strategy.theme !== strategy.category ? `Theme: ${strategy.theme}` : null,
    `Rank: ${strategy.rank}`,
    `Avg PnL/Trade: ${formatDollars(strategy.avg_pnl_per_trade)}`,
    `Weighted Avg PnL: ${formatDollars(strategy.weighted_avg_pnl)}`,
    `Trades: ${strategy.num_trades}`,
  ]
    .filter(Boolean)
    .join('\n');

  return (
    <div
      className="flex items-center justify-between rounded-md px-3 py-2 text-sm"
      style={{
        backgroundColor: colors.bg,
        borderLeft: `4px solid ${colors.border}`,
      }}
      title={tooltipText}
    >
      <div className="flex items-center gap-3 min-w-0">
        <span
          className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full text-xs font-bold"
          style={{
            backgroundColor: colors.border,
            color: '#ffffff',
          }}
        >
          {strategy.rank}
        </span>
        <div className="min-w-0">
          <div className="truncate font-medium text-[var(--text-primary)]">
            {strategy.category}
          </div>
          {strategy.theme !== strategy.category && (
            <div className="truncate text-xs text-[var(--text-secondary)]">{strategy.theme}</div>
          )}
        </div>
      </div>

      <div className="flex items-center gap-6 flex-shrink-0 text-right">
        <div>
          <div className="text-xs text-[var(--text-secondary)]">Trades</div>
          <div className="font-medium text-[var(--text-primary)]">{strategy.num_trades}</div>
        </div>
        <div>
          <div className="text-xs text-[var(--text-secondary)]">Avg PnL</div>
          <div className={`font-medium ${pnlTextClass(strategy.avg_pnl_per_trade)}`}>
            {formatDollars(strategy.avg_pnl_per_trade)}
          </div>
        </div>
        <div className="w-24">
          <div className="text-xs text-[var(--text-secondary)]">Weighted PnL</div>
          <div className={`font-bold ${pnlTextClass(strategy.weighted_avg_pnl)}`}>
            {formatDollars(strategy.weighted_avg_pnl)}
          </div>
        </div>
      </div>
    </div>
  );
}

function CategoryLegend({ categories }: { categories: string[] }) {
  if (categories.length === 0) return null;

  return (
    <div className="flex flex-wrap items-center gap-3 rounded-md border border-[var(--border-color)] bg-[var(--bg-secondary)] px-4 py-2">
      <span className="text-xs font-medium text-[var(--text-secondary)]">Categories:</span>
      {categories.map((cat) => {
        const hue = getCategoryHue(cat);
        const label = CATEGORY_LABELS[cat] ?? cat.replace(/_/g, ' ');
        return (
          <div key={cat} className="flex items-center gap-1.5">
            <span
              className="inline-block h-3 w-3 rounded-sm"
              style={{ backgroundColor: `hsl(${hue}, 100%, 45%)` }}
            />
            <span className="text-xs text-[var(--text-primary)] capitalize">{label}</span>
          </div>
        );
      })}
      <span className="ml-2 text-xs text-[var(--text-secondary)]">
        Brighter = better performance
      </span>
    </div>
  );
}

function ResultsSection({ data }: { data: StrategyProbeResponse }) {
  const categories = useMemo(() => collectCategories(data.weeks), [data.weeks]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="text-sm text-[var(--text-secondary)]">
          Showing <span className="font-medium text-[var(--text-primary)]">{data.weeks.length}</span> weeks
          for <span className="font-medium text-[var(--text-primary)]">{data.symbol}</span>
        </div>
      </div>
      <CategoryLegend categories={categories} />
      {data.weeks.map((week) => (
        <WeekCard key={week.week_start} week={week} />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function StrategyProbe() {
  const [symbol, setSymbol] = useState('');
  const [symbolInput, setSymbolInput] = useState('');
  const [startDate, setStartDate] = useState(defaultStartDate);
  const [endDate, setEndDate] = useState(todayStr);
  const [data, setData] = useState<StrategyProbeResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    if (!symbol) return;
    setLoading(true);
    setError(null);
    try {
      const result = await fetchStrategyProbe(symbol, startDate, endDate);
      setData(result);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load strategy probe data';
      setError(message);
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [symbol, startDate, endDate]);

  useEffect(() => {
    if (symbol) {
      loadData();
    }
  }, [symbol, startDate, endDate, loadData]);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = symbolInput.trim().toUpperCase();
    if (trimmed) {
      setSymbol(trimmed);
    }
  }

  return (
    <div className="p-6">
      <h1 className="mb-2 text-2xl font-semibold text-[var(--text-primary)]">Strategy Probe</h1>
      <p className="mb-6 text-sm text-[var(--text-secondary)]">
        Analyze weekly strategy performance rankings by ticker. See which strategies performed best
        each week based on weighted average PnL.
      </p>

      {/* Controls */}
      <form onSubmit={handleSubmit} className="mb-6 flex flex-wrap items-end gap-4">
        {/* Symbol input */}
        <div>
          <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">
            Symbol
          </label>
          <input
            type="text"
            value={symbolInput}
            onChange={(e) => setSymbolInput(e.target.value)}
            placeholder="e.g. AAPL"
            className="h-9 w-32 rounded-md border border-[var(--border-color)] bg-[var(--bg-secondary)] px-3 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-secondary)] focus:border-[var(--accent-blue)] focus:outline-none focus:ring-1 focus:ring-[var(--accent-blue)]"
          />
        </div>

        {/* Start date */}
        <div>
          <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">
            Start Date
          </label>
          <input
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            className="h-9 rounded-md border border-[var(--border-color)] bg-[var(--bg-secondary)] px-3 text-sm text-[var(--text-primary)] focus:border-[var(--accent-blue)] focus:outline-none focus:ring-1 focus:ring-[var(--accent-blue)]"
          />
        </div>

        {/* End date */}
        <div>
          <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">
            End Date
          </label>
          <input
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            className="h-9 rounded-md border border-[var(--border-color)] bg-[var(--bg-secondary)] px-3 text-sm text-[var(--text-primary)] focus:border-[var(--accent-blue)] focus:outline-none focus:ring-1 focus:ring-[var(--accent-blue)]"
          />
        </div>

        <button
          type="submit"
          disabled={!symbolInput.trim() || loading}
          className="h-9 rounded-md bg-[var(--accent-blue)] px-4 text-sm font-medium text-white transition-colors hover:bg-[var(--accent-blue)]/80 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? 'Loading...' : 'Analyze'}
        </button>
      </form>

      {/* Error state */}
      {error && (
        <div className="mb-4 rounded-md border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Loading state */}
      {loading && (
        <div className="flex items-center justify-center py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-[var(--accent-blue)] border-t-transparent" />
        </div>
      )}

      {/* Empty state */}
      {!loading && data && data.weeks.length === 0 && (
        <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-primary)] p-8 text-center">
          <p className="text-sm text-[var(--text-secondary)]">
            No closed campaigns found for <span className="font-medium text-[var(--text-primary)]">{data.symbol}</span> in the selected date range.
          </p>
        </div>
      )}

      {/* Results */}
      {!loading && data && data.weeks.length > 0 && (
        <ResultsSection data={data} />
      )}

      {/* Initial state */}
      {!loading && !data && !error && (
        <div className="rounded-lg border border-dashed border-[var(--border-color)] bg-[var(--bg-primary)] p-12 text-center">
          <p className="text-sm text-[var(--text-secondary)]">
            Enter a ticker symbol above and click Analyze to view weekly strategy rankings.
          </p>
        </div>
      )}
    </div>
  );
}
