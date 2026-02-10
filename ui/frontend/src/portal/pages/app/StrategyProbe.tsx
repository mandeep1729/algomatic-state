import { useEffect, useState, useCallback, useMemo } from 'react';
import { fetchStrategyProbe, fetchOHLCVData, fetchTopStrategies } from '../../api';
import type { StrategyProbeResponse, WeekPerformance, OHLCVData, TopStrategiesResponse, TopStrategyDetail } from '../../api';

function defaultStartDate(): string {
  const d = new Date();
  d.setMonth(d.getMonth() - 3);
  return d.toISOString().split('T')[0];
}

function todayStr(): string {
  return new Date().toISOString().split('T')[0];
}

// ---------------------------------------------------------------------------
// Theme color system — Tableau 10 palette for maximum distinguishability
// ---------------------------------------------------------------------------

const THEME_COLORS: Record<string, string> = {
  trend: '#4E79A7',
  mean_reversion: '#F28E2B',
  breakout: '#E15759',
  momentum: '#59A14F',
  volatility: '#B07AA1',
};

const THEME_LABELS: Record<string, string> = {
  trend: 'Trend',
  mean_reversion: 'Mean Reversion',
  breakout: 'Breakout',
  momentum: 'Momentum',
  volatility: 'Volatility',
};

const THEME_LETTERS: Record<string, string> = {
  trend: 'T',
  mean_reversion: 'R',
  breakout: 'B',
  momentum: 'M',
  volatility: 'V',
};

const FALLBACK_COLORS = ['#FF9DA7', '#9C755F', '#BAB0AC', '#76B7B2', '#EDC948'];

function normalize(theme: string): string {
  return theme.toLowerCase().replace(/\s+/g, '_');
}

function getThemeColor(theme: string): string {
  const n = normalize(theme);
  if (THEME_COLORS[n]) return THEME_COLORS[n];
  let hash = 0;
  for (let i = 0; i < n.length; i++) {
    hash = n.charCodeAt(i) + ((hash << 5) - hash);
    hash = hash & hash;
  }
  return FALLBACK_COLORS[((hash % FALLBACK_COLORS.length) + FALLBACK_COLORS.length) % FALLBACK_COLORS.length];
}

function getThemeLabel(theme: string): string {
  const n = normalize(theme);
  return THEME_LABELS[n] ?? theme.replace(/_/g, ' ');
}

function getThemeLetter(theme: string): string {
  const n = normalize(theme);
  return THEME_LETTERS[n] ?? n.charAt(0).toUpperCase();
}

function formatPct(val: number, decimals = 2): string {
  const sign = val >= 0 ? '+' : '';
  return `${sign}${(val * 100).toFixed(decimals)}%`;
}

function formatWeekLabel(weekStart: string): string {
  const d = new Date(weekStart + 'T00:00:00');
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function collectThemes(weeks: WeekPerformance[]): string[] {
  const seen = new Set<string>();
  for (const week of weeks) {
    for (const t of week.themes) seen.add(normalize(t.theme));
  }
  const knownOrder = Object.keys(THEME_COLORS);
  const known: string[] = [];
  const unknown: string[] = [];
  for (const t of seen) {
    if (knownOrder.includes(t)) known.push(t);
    else unknown.push(t);
  }
  known.sort((a, b) => knownOrder.indexOf(a) - knownOrder.indexOf(b));
  unknown.sort();
  return [...known, ...unknown];
}

/** Bucket OHLCV bars into per-week arrays aligned to probe week boundaries. */
interface WeekBars {
  timestamps: string[];
  open: number[];
  high: number[];
  low: number[];
  close: number[];
  volume: number[];
}

function bucketByWeek(
  ohlcv: OHLCVData,
  weeks: WeekPerformance[],
): Map<string, WeekBars> {
  const result = new Map<string, WeekBars>();
  for (const week of weeks) {
    result.set(week.week_start, {
      timestamps: [], open: [], high: [], low: [], close: [], volume: [],
    });
  }

  for (let i = 0; i < ohlcv.timestamps.length; i++) {
    const t = new Date(ohlcv.timestamps[i]).getTime();
    // Find which week this bar belongs to
    for (const week of weeks) {
      const ws = new Date(week.week_start + 'T00:00:00').getTime();
      const we = new Date(week.week_end + 'T23:59:59').getTime();
      if (t >= ws && t <= we) {
        const bucket = result.get(week.week_start)!;
        bucket.timestamps.push(ohlcv.timestamps[i]);
        bucket.open.push(ohlcv.open[i]);
        bucket.high.push(ohlcv.high[i]);
        bucket.low.push(ohlcv.low[i]);
        bucket.close.push(ohlcv.close[i]);
        bucket.volume.push(ohlcv.volume[i]);
        break;
      }
    }
  }

  return result;
}

// ---------------------------------------------------------------------------
// Components
// ---------------------------------------------------------------------------

function ThemeLegend({ themes }: { themes: string[] }) {
  if (themes.length === 0) return null;
  return (
    <div className="flex flex-wrap items-center gap-4 rounded-md border border-[var(--border-color)] bg-[var(--bg-secondary)] px-4 py-2.5">
      <span className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider">Legend</span>
      {themes.map((t) => (
        <div key={t} className="flex items-center gap-1.5">
          <div
            className="h-3 w-3 shrink-0 rounded-sm"
            style={{ backgroundColor: getThemeColor(t) }}
          />
          <span className="text-xs text-[var(--text-primary)]">{getThemeLabel(t)}</span>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Per-week candlestick cell (fits inside one grid column)
// ---------------------------------------------------------------------------

const CANDLE_H = 160;
const VOLUME_H = 70;
const BULL_COLOR = '#26a69a';
const BEAR_COLOR = '#ef5350';

function WeekCandles({
  bars,
  pLo,
  pHi,
  maxVol,
}: {
  bars: WeekBars;
  pLo: number;
  pHi: number;
  maxVol: number;
}) {
  const n = bars.timestamps.length;
  if (n === 0) {
    return <div style={{ height: CANDLE_H + VOLUME_H }} />;
  }

  const totalH = CANDLE_H + VOLUME_H;
  // Use a fixed viewBox width; SVG stretches to fill the grid column
  const vbW = Math.max(n * 10, 20);
  const colW = vbW / n;
  const bodyW = Math.max(colW * 0.6, 1.5);

  const toY = (price: number) =>
    ((pHi - price) / (pHi - pLo)) * CANDLE_H;
  const toVolY = (vol: number) =>
    CANDLE_H + VOLUME_H - (vol / maxVol) * (VOLUME_H - 2);

  return (
    <svg
      viewBox={`0 0 ${vbW} ${totalH}`}
      preserveAspectRatio="none"
      className="block w-full"
      style={{ height: totalH }}
    >
      {/* Volume bars */}
      {bars.timestamps.map((_, i) => {
        const bullish = bars.close[i] >= bars.open[i];
        const cx = colW * i + colW / 2;
        const vy = toVolY(bars.volume[i]);
        const vh = CANDLE_H + VOLUME_H - vy;
        return (
          <rect
            key={`v${i}`}
            x={cx - bodyW / 2}
            y={vy}
            width={bodyW}
            height={Math.max(vh, 0.5)}
            fill={bullish ? BULL_COLOR : BEAR_COLOR}
            opacity={0.7}
          />
        );
      })}

      {/* Separator */}
      <line
        x1={0} y1={CANDLE_H} x2={vbW} y2={CANDLE_H}
        stroke="var(--border-color)" strokeWidth={0.3}
      />

      {/* Candlesticks */}
      {bars.timestamps.map((ts, i) => {
        const o = bars.open[i];
        const c = bars.close[i];
        const h = bars.high[i];
        const l = bars.low[i];
        const bullish = c >= o;
        const color = bullish ? BULL_COLOR : BEAR_COLOR;
        const cx = colW * i + colW / 2;
        const bodyTop = toY(Math.max(o, c));
        const bodyBot = toY(Math.min(o, c));
        const bodyH = Math.max(bodyBot - bodyTop, 0.5);

        return (
          <g key={`c${i}`}>
            <line
              x1={cx} y1={toY(h)} x2={cx} y2={toY(l)}
              stroke={color} strokeWidth={1} vectorEffect="non-scaling-stroke"
            />
            <rect
              x={cx - bodyW / 2} y={bodyTop}
              width={bodyW} height={bodyH}
              fill={bullish ? 'transparent' : color}
              stroke={color} strokeWidth={1} vectorEffect="non-scaling-stroke"
            />
            <title>{`${new Date(ts).toLocaleString('en-US', { timeZone: 'America/New_York' })}\nO: $${o.toFixed(2)}  H: $${h.toFixed(2)}  L: $${l.toFixed(2)}  C: $${c.toFixed(2)}\nVol: ${bars.volume[i].toLocaleString()}`}</title>
          </g>
        );
      })}
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Theme detail modal — shows top 3 strategies for a theme within a week
// ---------------------------------------------------------------------------

interface ModalContext {
  theme: string;
  weekStart: string;
  weekEnd: string;
  avgPrice: number;
}

function ThemeDetailModal({
  context,
  data,
  loading,
  error,
  onClose,
}: {
  context: ModalContext;
  data: TopStrategiesResponse | null;
  loading: boolean;
  error: string | null;
  onClose: () => void;
}) {
  const n = normalize(context.theme);
  const color = getThemeColor(n);
  const label = getThemeLabel(n);
  const weekLabel = `${formatWeekLabel(context.weekStart)} – ${formatWeekLabel(context.weekEnd)}`;

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose();
    }
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
      onClick={onClose}
    >
      <div
        className="relative max-h-[85vh] w-full max-w-2xl overflow-y-auto rounded-lg border border-[var(--border-color)] bg-[var(--bg-primary)] p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="mb-5 flex items-start justify-between">
          <div className="flex items-center gap-3">
            <span
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg text-base font-bold text-white"
              style={{ backgroundColor: color }}
            >
              {getThemeLetter(n)}
            </span>
            <div>
              <h2 className="text-lg font-semibold text-[var(--text-primary)]">{label}</h2>
              <p className="text-xs text-[var(--text-secondary)]">Top strategies for week of {weekLabel}</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-secondary)] hover:text-[var(--text-primary)]"
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        {loading && (
          <div className="flex items-center justify-center py-12">
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-[var(--accent-blue)] border-t-transparent" />
          </div>
        )}

        {error && (
          <div className="rounded-md border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-400">
            {error}
          </div>
        )}

        {!loading && !error && data && data.strategies.length === 0 && (
          <p className="py-8 text-center text-sm text-[var(--text-secondary)]">
            No strategy data found for this theme and week.
          </p>
        )}

        {!loading && !error && data && data.strategies.length > 0 && (
          <div className="space-y-4">
            {data.strategies.map((strategy, idx) => (
              <TopStrategyCard
                key={strategy.name}
                strategy={strategy}
                rank={idx + 1}
                themeColor={color}
                avgPrice={context.avgPrice}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function TopStrategyCard({
  strategy,
  rank,
  themeColor,
  avgPrice,
}: {
  strategy: TopStrategyDetail;
  rank: number;
  themeColor: string;
  avgPrice: number;
}) {
  const d = strategy.details ?? {};
  const entryLong = (d.entry_long as string) || '';
  const entryShort = (d.entry_short as string) || '';
  const exit = (d.exit as string) || '';
  const indicators = (d.indicators ?? []) as string[];
  const isProfit = strategy.weighted_avg_pnl >= 0;

  // Avg/Trade($) = avgPrice * weighted_avg_pnl / num_trades (rounded to 3 decimals)
  const avgTradeUsd = strategy.num_trades > 0
    ? (avgPrice * strategy.weighted_avg_pnl / strategy.num_trades)
    : 0;

  return (
    <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] overflow-hidden">
      {/* Card header: rank + name + direction badge */}
      <div className="flex items-center gap-3 border-b border-[var(--border-color)] px-4 py-3">
        <span
          className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold text-white"
          style={{ backgroundColor: themeColor }}
        >
          #{rank}
        </span>
        <h3 className="flex-1 text-sm font-semibold text-[var(--text-primary)]">{strategy.display_name}</h3>
        <span
          className="shrink-0 rounded-full px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-white"
          style={{ backgroundColor: themeColor, opacity: 0.85 }}
        >
          {strategy.direction}
        </span>
      </div>

      <div className="px-4 py-3 space-y-3">
        {/* Performance metrics */}
        <div className="flex gap-3">
          <div className="rounded-md border border-[var(--border-color)] bg-[var(--bg-primary)] px-3 py-2 flex-1 text-center">
            <div className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">Trades</div>
            <div className="text-sm font-bold text-[var(--text-primary)]">{strategy.num_trades}</div>
          </div>
          <div className="rounded-md border border-[var(--border-color)] bg-[var(--bg-primary)] px-3 py-2 flex-1 text-center">
            <div className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">Return</div>
            <div className={`text-sm font-bold ${isProfit ? 'text-[#26a69a]' : 'text-[#ef5350]'}`}>
              {formatPct(strategy.weighted_avg_pnl)}
            </div>
          </div>
          <div className="rounded-md border border-[var(--border-color)] bg-[var(--bg-primary)] px-3 py-2 flex-1 text-center">
            <div className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">Avg/Trade</div>
            <div className={`text-sm font-bold ${avgTradeUsd >= 0 ? 'text-[#26a69a]' : 'text-[#ef5350]'}`}>
              ${avgTradeUsd.toFixed(3)}
            </div>
          </div>
        </div>

        {/* Philosophy */}
        <div>
          <h4 className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">Philosophy</h4>
          <p className="text-xs leading-relaxed text-[var(--text-primary)]">{strategy.philosophy}</p>
        </div>

        {/* Indicators */}
        {indicators.length > 0 && (
          <div>
            <h4 className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">Indicators</h4>
            <div className="flex flex-wrap gap-1.5">
              {indicators.map((ind, i) => (
                <span
                  key={i}
                  className="rounded-md border border-[var(--border-color)] bg-[var(--bg-primary)] px-2 py-0.5 text-[11px] font-mono text-[var(--text-primary)]"
                >
                  {ind}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Entry / Exit signals */}
        <div className="space-y-2">
          {entryLong && (
            <div className="flex items-start gap-2">
              <span className="mt-0.5 shrink-0 rounded bg-[#26a69a]/20 px-1.5 py-0.5 text-[10px] font-bold text-[#26a69a]">LONG</span>
              <p className="text-xs leading-relaxed text-[var(--text-primary)]">{entryLong}</p>
            </div>
          )}
          {entryShort && (
            <div className="flex items-start gap-2">
              <span className="mt-0.5 shrink-0 rounded bg-[#ef5350]/20 px-1.5 py-0.5 text-[10px] font-bold text-[#ef5350]">SHORT</span>
              <p className="text-xs leading-relaxed text-[var(--text-primary)]">{entryShort}</p>
            </div>
          )}
          {exit && (
            <div className="flex items-start gap-2">
              <span className="mt-0.5 shrink-0 rounded bg-[var(--text-secondary)]/20 px-1.5 py-0.5 text-[10px] font-bold text-[var(--text-secondary)]">EXIT</span>
              <p className="text-xs leading-relaxed text-[var(--text-primary)]">{exit}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Theme bands
// ---------------------------------------------------------------------------

function ThemeBand({
  theme,
  weekStart,
  weekEnd,
  showThemeNames,
  onClick,
}: {
  theme: { theme: string; rank: number; weighted_avg_pnl: number; num_trades: number; avg_pnl_per_trade: number };
  weekStart: string;
  weekEnd: string;
  showThemeNames: boolean;
  onClick: (theme: string, weekStart: string, weekEnd: string) => void;
}) {
  const n = normalize(theme.theme);
  const color = getThemeColor(n);
  const isPositive = theme.weighted_avg_pnl >= 0;

  return (
    <div
      className="flex cursor-pointer items-center justify-center overflow-hidden transition-opacity hover:opacity-80"
      style={{
        flex: 1,
        backgroundColor: `${color}${isPositive ? '33' : '18'}`,
        borderLeft: `3px solid ${color}`,
      }}
      title={`${getThemeLetter(n)} - ${getThemeLabel(n)}\nRank: #${theme.rank}\nP&L: ${formatPct(theme.weighted_avg_pnl)}\nTrades: ${theme.num_trades}\nClick for top strategies`}
      onClick={() => onClick(n, weekStart, weekEnd)}
    >
      <span
        className="text-[12px] font-bold truncate px-1"
        style={{ color }}
      >
        {showThemeNames ? getThemeLabel(n) : getThemeLetter(n)}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Combined grid: candlestick row + week headers + theme stacks — all aligned
// ---------------------------------------------------------------------------

function StackedTimeline({
  data,
  ohlcv,
}: {
  data: StrategyProbeResponse;
  ohlcv: OHLCVData | null;
}) {
  const [showThemeNames, setShowThemeNames] = useState(false);
  const [modalContext, setModalContext] = useState<ModalContext | null>(null);
  const [topData, setTopData] = useState<TopStrategiesResponse | null>(null);
  const [topLoading, setTopLoading] = useState(false);
  const [topError, setTopError] = useState<string | null>(null);

  const handleThemeClick = useCallback(async (theme: string, weekStart: string, weekEnd: string) => {
    // Compute average close price from OHLCV data for this week
    let avgPrice = 0;
    if (ohlcv && ohlcv.timestamps.length > 0) {
      const ws = new Date(weekStart + 'T00:00:00').getTime();
      const we = new Date(weekEnd + 'T23:59:59').getTime();
      let sum = 0;
      let count = 0;
      for (let i = 0; i < ohlcv.timestamps.length; i++) {
        const t = new Date(ohlcv.timestamps[i]).getTime();
        if (t >= ws && t <= we) {
          sum += ohlcv.close[i];
          count++;
        }
      }
      if (count > 0) avgPrice = sum / count;
    }

    setModalContext({ theme, weekStart, weekEnd, avgPrice });
    setTopData(null);
    setTopError(null);
    setTopLoading(true);
    try {
      const result = await fetchTopStrategies(data.symbol, theme, weekStart, weekEnd);
      setTopData(result);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load top strategies';
      setTopError(message);
    } finally {
      setTopLoading(false);
    }
  }, [data.symbol, ohlcv]);

  const handleModalClose = useCallback(() => {
    setModalContext(null);
    setTopData(null);
    setTopError(null);
  }, []);

  const themes = useMemo(() => collectThemes(data.weeks), [data.weeks]);
  const maxThemeCount = useMemo(
    () => Math.max(...data.weeks.map((w) => w.themes.length), 1),
    [data.weeks],
  );

  // Bucket OHLCV bars by week and compute global ranges
  const weekBuckets = useMemo(
    () => (ohlcv ? bucketByWeek(ohlcv, data.weeks) : null),
    [ohlcv, data.weeks],
  );

  const { pLo, pHi, maxVol } = useMemo(() => {
    if (!ohlcv || ohlcv.timestamps.length === 0) {
      return { pLo: 0, pHi: 1, maxVol: 1 };
    }
    const lo = Math.min(...ohlcv.low);
    const hi = Math.max(...ohlcv.high);
    return {
      pLo: lo,
      pHi: hi === lo ? hi + 1 : hi,
      maxVol: Math.max(...ohlcv.volume, 1),
    };
  }, [ohlcv]);

  const colTemplate = `repeat(${data.weeks.length}, minmax(48px, 1fr))`;
  const BAND_HEIGHT = 28;
  const stackHeight = maxThemeCount * BAND_HEIGHT;
  const hasCandles = weekBuckets !== null;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="text-sm text-[var(--text-secondary)]">
          Showing <span className="font-medium text-[var(--text-primary)]">{data.weeks.length}</span> weeks
          for <span className="font-medium text-[var(--text-primary)]">{data.symbol}</span>
        </div>
        <button
          type="button"
          onClick={() => setShowThemeNames((prev) => !prev)}
          className="rounded-md border border-[var(--border-color)] bg-[var(--bg-secondary)] px-2.5 py-1 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-primary)] hover:text-[var(--text-primary)]"
        >
          {showThemeNames ? 'Show Letters' : 'Show Names'}
        </button>
      </div>
      <ThemeLegend themes={themes} />

      <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-primary)]">
        <div className="grid gap-0" style={{ gridTemplateColumns: colTemplate }}>
          {/* Row 1: Candlestick + volume per week (aligned columns) */}
          {hasCandles && data.weeks.map((week) => (
            <div
              key={`candle-${week.week_start}`}
              className="border-b border-r border-[var(--border-color)] last:border-r-0"
            >
              <WeekCandles
                bars={weekBuckets.get(week.week_start) ?? { timestamps: [], open: [], high: [], low: [], close: [], volume: [] }}
                pLo={pLo}
                pHi={pHi}
                maxVol={maxVol}
              />
            </div>
          ))}

          {/* Row 2: Week headers */}
          {data.weeks.map((week) => (
            <div
              key={week.week_start}
              className="border-b border-r border-[var(--border-color)] px-1 py-1 text-center last:border-r-0"
            >
              <div className="text-[10px] font-semibold text-[var(--text-primary)]">
                {formatWeekLabel(week.week_start)}
              </div>
            </div>
          ))}

          {/* Row 3: Theme stack per week */}
          {data.weeks.map((week) => (
            <div
              key={`stack-${week.week_start}`}
              className="flex flex-col border-r border-[var(--border-color)] last:border-r-0"
              style={{ height: stackHeight }}
            >
              {week.themes.map((theme) => (
                <ThemeBand
                  key={`${week.week_start}-${theme.theme}`}
                  theme={theme}
                  weekStart={week.week_start}
                  weekEnd={week.week_end}
                  showThemeNames={showThemeNames}
                  onClick={handleThemeClick}
                />
              ))}
            </div>
          ))}
        </div>
      </div>

      {modalContext && (
        <ThemeDetailModal
          context={modalContext}
          data={topData}
          loading={topLoading}
          error={topError}
          onClose={handleModalClose}
        />
      )}
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
  const [timeframe, setTimeframe] = useState('');
  const [availableTimeframes, setAvailableTimeframes] = useState<string[]>([]);
  const [data, setData] = useState<StrategyProbeResponse | null>(null);
  const [ohlcv, setOhlcv] = useState<OHLCVData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    if (!symbol) return;
    setLoading(true);
    setError(null);
    try {
      const [probeResult, ohlcvResult] = await Promise.all([
        fetchStrategyProbe(symbol, startDate, endDate, timeframe || undefined),
        fetchOHLCVData(symbol, '1Hour', startDate, endDate).catch(() => null),
      ]);
      setData(probeResult);
      setOhlcv(ohlcvResult);
      // Update available timeframes from response
      if (probeResult.available_timeframes) {
        setAvailableTimeframes(probeResult.available_timeframes);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load strategy probe data';
      setError(message);
      setData(null);
      setOhlcv(null);
    } finally {
      setLoading(false);
    }
  }, [symbol, startDate, endDate, timeframe]);

  useEffect(() => {
    if (symbol) {
      loadData();
    }
  }, [symbol, startDate, endDate, timeframe, loadData]);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = symbolInput.trim().toUpperCase();
    if (trimmed) {
      // Reset timeframe when symbol changes to avoid stale filter
      if (trimmed !== symbol) {
        setTimeframe('');
        setAvailableTimeframes([]);
      }
      setSymbol(trimmed);
    }
  }

  return (
    <div className="p-6">
      <h1 className="mb-2 text-2xl font-semibold text-[var(--text-primary)]">Strategy Probe</h1>
      <p className="mb-6 text-sm text-[var(--text-secondary)]">
        Weekly strategy theme performance. Candlestick chart shows hourly price action; theme bands show rank order (best on top).
      </p>

      <form onSubmit={handleSubmit} className="mb-6 flex flex-wrap items-end gap-4">
        <div>
          <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">Symbol</label>
          <input
            type="text"
            value={symbolInput}
            onChange={(e) => setSymbolInput(e.target.value)}
            placeholder="e.g. AAPL"
            className="h-9 w-32 rounded-md border border-[var(--border-color)] bg-[var(--bg-secondary)] px-3 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-secondary)] focus:border-[var(--accent-blue)] focus:outline-none focus:ring-1 focus:ring-[var(--accent-blue)]"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">Start Date</label>
          <input
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            className="h-9 rounded-md border border-[var(--border-color)] bg-[var(--bg-secondary)] px-3 text-sm text-[var(--text-primary)] focus:border-[var(--accent-blue)] focus:outline-none focus:ring-1 focus:ring-[var(--accent-blue)]"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">End Date</label>
          <input
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            className="h-9 rounded-md border border-[var(--border-color)] bg-[var(--bg-secondary)] px-3 text-sm text-[var(--text-primary)] focus:border-[var(--accent-blue)] focus:outline-none focus:ring-1 focus:ring-[var(--accent-blue)]"
          />
        </div>
        {availableTimeframes.length > 0 && (
          <div>
            <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">Timeframe</label>
            <select
              value={timeframe}
              onChange={(e) => setTimeframe(e.target.value)}
              className="h-9 rounded-md border border-[var(--border-color)] bg-[var(--bg-secondary)] px-3 text-sm text-[var(--text-primary)] focus:border-[var(--accent-blue)] focus:outline-none focus:ring-1 focus:ring-[var(--accent-blue)]"
            >
              <option value="">All Timeframes</option>
              {availableTimeframes.map((tf) => (
                <option key={tf} value={tf}>{tf}</option>
              ))}
            </select>
          </div>
        )}
        <button
          type="submit"
          disabled={!symbolInput.trim() || loading}
          className="h-9 rounded-md bg-[var(--accent-blue)] px-4 text-sm font-medium text-white transition-colors hover:bg-[var(--accent-blue)]/80 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? 'Loading...' : 'Analyze'}
        </button>
      </form>

      {error && (
        <div className="mb-4 rounded-md border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-400">
          {error}
        </div>
      )}

      {loading && (
        <div className="flex items-center justify-center py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-[var(--accent-blue)] border-t-transparent" />
        </div>
      )}

      {!loading && data && data.weeks.length === 0 && (
        <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-primary)] p-8 text-center">
          <p className="text-sm text-[var(--text-secondary)]">
            No probe results found for <span className="font-medium text-[var(--text-primary)]">{data.symbol}</span> in the selected date range.
          </p>
        </div>
      )}

      {!loading && data && data.weeks.length > 0 && (
        <StackedTimeline data={data} ohlcv={ohlcv} />
      )}

      {!loading && !data && !error && (
        <div className="rounded-lg border border-dashed border-[var(--border-color)] bg-[var(--bg-primary)] p-12 text-center">
          <p className="text-sm text-[var(--text-secondary)]">
            Enter a ticker symbol above and click Analyze to view weekly strategy theme rankings.
          </p>
        </div>
      )}
    </div>
  );
}
