import { useEffect, useState, useCallback, useMemo } from 'react';
import { fetchStrategyProbe, fetchOHLCVData } from '../../api';
import type { StrategyProbeResponse, WeekPerformance, OHLCVData } from '../../api';

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

// Fallback colors for unknown themes
const FALLBACK_COLORS = ['#FF9DA7', '#9C755F', '#BAB0AC', '#76B7B2', '#EDC948'];

function normalize(theme: string): string {
  return theme.toLowerCase().replace(/\s+/g, '_');
}

function getThemeColor(theme: string): string {
  const n = normalize(theme);
  if (THEME_COLORS[n]) return THEME_COLORS[n];
  // Deterministic fallback based on string hash
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

function formatDollars(val: number): string {
  const sign = val >= 0 ? '+' : '';
  return `${sign}$${val.toFixed(2)}`;
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

// ---------------------------------------------------------------------------
// Components
// ---------------------------------------------------------------------------

/** Legend: color badge + letter + full name per theme. */
function ThemeLegend({ themes }: { themes: string[] }) {
  if (themes.length === 0) return null;
  return (
    <div className="flex flex-wrap items-center gap-4 rounded-md border border-[var(--border-color)] bg-[var(--bg-secondary)] px-4 py-2.5">
      <span className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider">Legend</span>
      {themes.map((t) => (
        <div key={t} className="flex items-center gap-1.5">
          <span
            className="flex h-5 w-5 items-center justify-center rounded text-[11px] font-bold text-white"
            style={{ backgroundColor: getThemeColor(t) }}
          >
            {getThemeLetter(t)}
          </span>
          <span className="text-xs text-[var(--text-primary)]">{getThemeLabel(t)}</span>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Candlestick chart with volume
// ---------------------------------------------------------------------------

const CANDLE_H = 180;
const VOLUME_H = 50;
const CHART_PAD_TOP = 8;
const CHART_PAD_BOTTOM = 4;
const BULL_COLOR = '#26a69a';
const BEAR_COLOR = '#ef5350';

function CandlestickChart({ ohlcv, symbol }: { ohlcv: OHLCVData; symbol: string }) {
  const n = ohlcv.timestamps.length;
  if (n === 0) return null;

  const svgW = Math.max(n * 8, 600);
  const totalH = CANDLE_H + VOLUME_H;
  const colW = svgW / n;
  const bodyW = Math.max(colW * 0.6, 2);

  // Price range
  const allHigh = ohlcv.high;
  const allLow = ohlcv.low;
  const minPrice = Math.min(...allLow);
  const maxPrice = Math.max(...allHigh);
  const priceRange = maxPrice - minPrice || 1;
  const pPad = priceRange * 0.05;
  const pLo = minPrice - pPad;
  const pHi = maxPrice + pPad;

  // Volume range
  const maxVol = Math.max(...ohlcv.volume, 1);

  const toY = (price: number) =>
    CHART_PAD_TOP + ((pHi - price) / (pHi - pLo)) * (CANDLE_H - CHART_PAD_TOP - CHART_PAD_BOTTOM);
  const toVolY = (vol: number) =>
    CANDLE_H + VOLUME_H - (vol / maxVol) * (VOLUME_H - 4);

  // Price gridlines (4 levels)
  const priceGridlines = Array.from({ length: 4 }, (_, i) => {
    const frac = (i + 1) / 5;
    const price = pLo + (pHi - pLo) * (1 - frac);
    return { y: toY(price), price };
  });

  // Format hourly x-axis labels — show day boundaries
  const dayLabels: { x: number; label: string }[] = [];
  let lastDay = '';
  for (let i = 0; i < n; i++) {
    const d = new Date(ohlcv.timestamps[i]);
    const dayStr = d.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      timeZone: 'America/New_York',
    });
    if (dayStr !== lastDay) {
      dayLabels.push({ x: colW * i + colW / 2, label: dayStr });
      lastDay = dayStr;
    }
  }

  return (
    <div className="overflow-x-auto">
      <div className="flex items-center gap-2 px-3 pt-2 pb-1">
        <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
          {symbol} Hourly OHLCV
        </span>
      </div>
      <svg
        viewBox={`0 0 ${svgW} ${totalH}`}
        preserveAspectRatio="none"
        className="w-full"
        style={{ height: totalH, minWidth: Math.max(n * 4, 400) }}
      >
        {/* Price gridlines */}
        {priceGridlines.map((g, i) => (
          <g key={i}>
            <line
              x1={0} y1={g.y} x2={svgW} y2={g.y}
              stroke="var(--border-color)" strokeWidth={0.5} strokeDasharray="4,4"
            />
            <text
              x={svgW - 4} y={g.y - 3}
              textAnchor="end"
              fontSize={9}
              fill="var(--text-secondary)"
              style={{ vectorEffect: 'non-scaling-stroke' }}
            >
              ${g.price.toFixed(2)}
            </text>
          </g>
        ))}

        {/* Separator between candle and volume */}
        <line
          x1={0} y1={CANDLE_H} x2={svgW} y2={CANDLE_H}
          stroke="var(--border-color)" strokeWidth={0.5}
        />

        {/* Day boundary labels */}
        {dayLabels.map((dl, i) => (
          <g key={i}>
            <line
              x1={dl.x - colW / 2} y1={0}
              x2={dl.x - colW / 2} y2={totalH}
              stroke="var(--border-color)" strokeWidth={0.3} strokeDasharray="2,6"
            />
          </g>
        ))}

        {/* Volume bars */}
        {ohlcv.timestamps.map((_, i) => {
          const bullish = ohlcv.close[i] >= ohlcv.open[i];
          const cx = colW * i + colW / 2;
          const vy = toVolY(ohlcv.volume[i]);
          const vh = CANDLE_H + VOLUME_H - vy;
          return (
            <rect
              key={`vol-${i}`}
              x={cx - bodyW / 2}
              y={vy}
              width={bodyW}
              height={Math.max(vh, 0.5)}
              fill={bullish ? BULL_COLOR : BEAR_COLOR}
              opacity={0.3}
            />
          );
        })}

        {/* Candlesticks */}
        {ohlcv.timestamps.map((ts, i) => {
          const o = ohlcv.open[i];
          const c = ohlcv.close[i];
          const h = ohlcv.high[i];
          const l = ohlcv.low[i];
          const bullish = c >= o;
          const color = bullish ? BULL_COLOR : BEAR_COLOR;
          const cx = colW * i + colW / 2;
          const bodyTop = toY(Math.max(o, c));
          const bodyBot = toY(Math.min(o, c));
          const bodyH = Math.max(bodyBot - bodyTop, 0.5);

          return (
            <g key={`candle-${i}`}>
              {/* Wick */}
              <line
                x1={cx} y1={toY(h)}
                x2={cx} y2={toY(l)}
                stroke={color}
                strokeWidth={1}
                vectorEffect="non-scaling-stroke"
              />
              {/* Body */}
              <rect
                x={cx - bodyW / 2}
                y={bodyTop}
                width={bodyW}
                height={bodyH}
                fill={bullish ? 'transparent' : color}
                stroke={color}
                strokeWidth={1}
                vectorEffect="non-scaling-stroke"
              />
              <title>{`${new Date(ts).toLocaleString('en-US', { timeZone: 'America/New_York' })}\nO: $${o.toFixed(2)}  H: $${h.toFixed(2)}  L: $${l.toFixed(2)}  C: $${c.toFixed(2)}\nVol: ${ohlcv.volume[i].toLocaleString()}`}</title>
            </g>
          );
        })}
      </svg>

      {/* Day labels below the chart */}
      <div className="relative w-full overflow-hidden" style={{ minWidth: Math.max(n * 4, 400), height: 18 }}>
        <svg viewBox={`0 0 ${svgW} 18`} preserveAspectRatio="none" className="w-full h-full">
          {dayLabels.map((dl, i) => (
            <text
              key={i}
              x={dl.x}
              y={12}
              textAnchor="middle"
              fontSize={9}
              fill="var(--text-secondary)"
            >
              {dl.label}
            </text>
          ))}
        </svg>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Theme bands
// ---------------------------------------------------------------------------

/** Full-width theme band for a single theme in a week column. */
function ThemeBand({
  theme,
}: {
  theme: { theme: string; rank: number; weighted_avg_pnl: number; num_trades: number; avg_pnl_per_trade: number };
}) {
  const n = normalize(theme.theme);
  const color = getThemeColor(n);
  const isPositive = theme.weighted_avg_pnl >= 0;

  return (
    <div
      className="flex items-center justify-center"
      style={{
        flex: 1,
        backgroundColor: `${color}${isPositive ? '33' : '18'}`, // 20% or 9% opacity via hex alpha
        borderLeft: `3px solid ${color}`,
      }}
      title={`${getThemeLetter(n)} - ${getThemeLabel(n)}\nRank: #${theme.rank}\nProfit: ${formatDollars(theme.weighted_avg_pnl)}\nTrades: ${theme.num_trades}`}
    >
      <span
        className="text-[12px] font-bold"
        style={{ color }}
      >
        {getThemeLetter(n)}
      </span>
    </div>
  );
}

/** Combined chart: candlestick on top, theme stack below. */
function StackedTimeline({
  data,
  ohlcv,
}: {
  data: StrategyProbeResponse;
  ohlcv: OHLCVData | null;
}) {
  const themes = useMemo(() => collectThemes(data.weeks), [data.weeks]);
  const maxThemeCount = useMemo(
    () => Math.max(...data.weeks.map((w) => w.themes.length), 1),
    [data.weeks],
  );

  const colTemplate = `repeat(${data.weeks.length}, minmax(48px, 1fr))`;
  const BAND_HEIGHT = 28;
  const stackHeight = maxThemeCount * BAND_HEIGHT;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="text-sm text-[var(--text-secondary)]">
          Showing <span className="font-medium text-[var(--text-primary)]">{data.weeks.length}</span> weeks
          for <span className="font-medium text-[var(--text-primary)]">{data.symbol}</span>
        </div>
      </div>
      <ThemeLegend themes={themes} />

      <div className="overflow-x-auto rounded-lg border border-[var(--border-color)] bg-[var(--bg-primary)]">
        {/* Candlestick chart */}
        {ohlcv && ohlcv.timestamps.length > 0 && (
          <div className="border-b border-[var(--border-color)]">
            <CandlestickChart ohlcv={ohlcv} symbol={data.symbol} />
          </div>
        )}

        {/* Grid: week headers + theme stacks */}
        <div className="grid gap-0" style={{ gridTemplateColumns: colTemplate }}>
          {/* Week headers */}
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

          {/* Theme stack: full-width bands per week */}
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
                />
              ))}
            </div>
          ))}
        </div>
      </div>
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
  const [ohlcv, setOhlcv] = useState<OHLCVData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    if (!symbol) return;
    setLoading(true);
    setError(null);
    try {
      const [probeResult, ohlcvResult] = await Promise.all([
        fetchStrategyProbe(symbol, startDate, endDate),
        fetchOHLCVData(symbol, '1Hour', startDate, endDate).catch(() => null),
      ]);
      setData(probeResult);
      setOhlcv(ohlcvResult);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load strategy probe data';
      setError(message);
      setData(null);
      setOhlcv(null);
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
