import { useEffect, useRef, useCallback, useMemo } from 'react';
import * as echarts from 'echarts/core';
import { CandlestickChart, BarChart, LineChart, CustomChart } from 'echarts/charts';
import {
  GridComponent,
  TooltipComponent,
  DataZoomComponent,
  LegendComponent,
  MarkLineComponent,
} from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import type { EChartsOption } from 'echarts';

type EChartsInstance = ReturnType<typeof echarts.init>;

// Register only what we need for tree-shaking
echarts.use([
  CandlestickChart,
  BarChart,
  LineChart,
  CustomChart,
  GridComponent,
  TooltipComponent,
  DataZoomComponent,
  LegendComponent,
  MarkLineComponent,
  CanvasRenderer,
]);

const MAX_CHART_POINTS = 7200;

interface OHLCVData {
  timestamps: string[];
  open: number[];
  high: number[];
  low: number[];
  close: number[];
  volume: number[];
}

interface FeatureData {
  timestamps: string[];
  features: Record<string, number[]>;
  feature_names: string[];
}

interface StateInfo {
  state_id: number;
  label: string;
  short_label: string;
  color: string;
  description: string;
}

interface RegimeData {
  timestamps: string[];
  state_ids: number[];
  state_info: Record<string, StateInfo>;
}

interface PnlData {
  timestamps: string[];
  cumulative_pnl: number[];
}

interface OHLCVChartProps {
  data: OHLCVData | null;
  featureData?: FeatureData | null;
  regimeData?: RegimeData | null;
  pnlData?: PnlData | null;
  selectedFeatures?: string[];
  showVolume?: boolean;
  showStates?: boolean;
  height?: number;
  onRangeChange?: (start: number, end: number) => void;
}

// Feature overlay colors
const OVERLAY_COLORS = [
  '#58a6ff', '#3fb950', '#f85149', '#d29922', '#a371f7',
  '#db6d28', '#ff7b72', '#7ee787', '#79c0ff', '#cea5fb',
];

// EST formatter — reusable across tooltip and axis labels
const estDateFmt = new Intl.DateTimeFormat('en-US', {
  timeZone: 'America/New_York',
  month: 'short',
  day: 'numeric',
});
const estTimeFmt = new Intl.DateTimeFormat('en-US', {
  timeZone: 'America/New_York',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
});
const estFullFmt = new Intl.DateTimeFormat('en-US', {
  timeZone: 'America/New_York',
  month: 'short',
  day: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
});

/** Format an ISO timestamp to an EST label for the x-axis. */
function formatTimestampEST(iso: string): string {
  const d = new Date(iso);
  return `${estDateFmt.format(d)} ${estTimeFmt.format(d)}`;
}

/** Check if feature should overlay on the price chart (vs. separate pane). */
function isPriceScaleFeature(featureKey: string): boolean {
  const priceFeatures = [
    'sma_20', 'sma_50', 'sma_200', 'ema_20', 'ema_50', 'ema_200',
    'bb_upper', 'bb_middle', 'bb_lower', 'vwap', 'vwap_60',
    'psar', 'ichi_tenkan', 'ichi_kijun', 'ichi_senkou_a', 'ichi_senkou_b',
    'pivot_pp', 'pivot_r1', 'pivot_r2', 'pivot_s1', 'pivot_s2',
  ];
  return priceFeatures.includes(featureKey);
}

/**
 * Align feature/regime timestamps to the OHLCV category axis.
 * Returns an array of values (or null for gaps) indexed by the category axis.
 */
function alignToCategories<T>(
  categoryTimestamps: string[],
  sourceTimestamps: string[],
  sourceValues: T[],
  nullValue: T,
): T[] {
  const map = new Map<string, T>();
  for (let i = 0; i < sourceTimestamps.length; i++) {
    map.set(sourceTimestamps[i], sourceValues[i]);
  }
  return categoryTimestamps.map((ts) => map.get(ts) ?? nullValue);
}

export function OHLCVChart({
  data,
  featureData,
  regimeData,
  pnlData,
  selectedFeatures = [],
  showVolume = true,
  showStates = true,
  height = 500,
  onRangeChange,
}: OHLCVChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const echartsRef = useRef<EChartsInstance | null>(null);

  // ── Data windowing: last MAX_CHART_POINTS ──
  const windowedData = useMemo(() => {
    if (!data) return null;
    const len = data.timestamps.length;
    if (len <= MAX_CHART_POINTS) return data;
    const start = len - MAX_CHART_POINTS;
    return {
      timestamps: data.timestamps.slice(start),
      open: data.open.slice(start),
      high: data.high.slice(start),
      low: data.low.slice(start),
      close: data.close.slice(start),
      volume: data.volume.slice(start),
    };
  }, [data]);

  // Category labels for the x-axis
  const categoryLabels = useMemo(
    () => (windowedData ? windowedData.timestamps.map(formatTimestampEST) : []),
    [windowedData],
  );

  // ── Build full ECharts option ──
  const chartOption = useMemo((): EChartsOption | null => {
    if (!windowedData) return null;

    const ts = windowedData.timestamps;
    const len = ts.length;

    // Determine which panes are active
    const hasVolume = showVolume;
    const hasStates = showStates && regimeData && regimeData.state_ids.length > 0;
    const nonPriceFeatures = selectedFeatures.filter((f) => !isPriceScaleFeature(f));
    const hasIndicatorPane = nonPriceFeatures.length > 0;
    const hasPnl = pnlData && pnlData.cumulative_pnl.length > 0;

    // ── Grid layout computation ──
    // Each grid is positioned via top/height percentages.
    const grids: EChartsOption['grid'] = [];
    const xAxes: EChartsOption['xAxis'] = [];
    const yAxes: EChartsOption['yAxis'] = [];

    // Spacing
    const topPad = 40; // px for buttons/legend
    const bottomPad = 5; // px
    const gapPx = 8;
    // We'll use pixel-based positioning for simplicity
    const totalHeight = height;
    const usable = totalHeight - topPad - bottomPad;

    // Pane height allocation (fractions of usable)
    let volumeFrac = hasVolume ? 0.15 : 0;
    let stateFrac = hasStates ? 0.06 : 0;
    let indicatorFrac = hasIndicatorPane ? 0.18 : 0;
    let pnlFrac = hasPnl ? 0.15 : 0;
    let priceFrac = 1 - volumeFrac - stateFrac - indicatorFrac - pnlFrac;

    // Convert to pixels
    const gapCount = [hasVolume, hasStates, hasIndicatorPane, hasPnl].filter(Boolean).length;
    const gapTotal = gapCount * gapPx;
    const avail = usable - gapTotal;

    const priceH = Math.round(avail * priceFrac);
    const volumeH = Math.round(avail * volumeFrac);
    const stateH = Math.round(avail * stateFrac);
    const indicatorH = Math.round(avail * indicatorFrac);
    const pnlH = Math.round(avail * pnlFrac);

    let curTop = topPad;
    let gridIdx = 0;

    // Grid 0: Candlestick + price-scale features
    const priceGridIdx = gridIdx++;
    grids.push({ left: 60, right: 60, top: curTop, height: priceH });
    curTop += priceH + gapPx;

    // Grid: Cumulative PnL
    let pnlGridIdx = -1;
    if (hasPnl) {
      pnlGridIdx = gridIdx++;
      grids.push({ left: 60, right: 60, top: curTop, height: pnlH });
      curTop += pnlH + gapPx;
    }

    // Grid: Volume
    let volumeGridIdx = -1;
    if (hasVolume) {
      volumeGridIdx = gridIdx++;
      grids.push({ left: 60, right: 60, top: curTop, height: volumeH });
      curTop += volumeH + gapPx;
    }

    // Grid: Regime states
    let stateGridIdx = -1;
    if (hasStates) {
      stateGridIdx = gridIdx++;
      grids.push({ left: 60, right: 60, top: curTop, height: stateH });
      curTop += stateH + gapPx;
    }

    // Grid: Non-price indicator overlays
    let indicatorGridIdx = -1;
    if (hasIndicatorPane) {
      indicatorGridIdx = gridIdx++;
      grids.push({ left: 60, right: 60, top: curTop, height: indicatorH });
      curTop += indicatorH + gapPx;
    }

    // Build x/y axes for each grid
    const allGridIndices: number[] = [];
    for (let g = 0; g < gridIdx; g++) {
      allGridIndices.push(g);
      (xAxes as any[]).push({
        type: 'category',
        data: categoryLabels,
        gridIndex: g,
        axisLabel: {
          show: g === gridIdx - 1, // only bottom grid shows labels
          color: '#8b949e',
          fontSize: 10,
        },
        axisTick: { show: g === gridIdx - 1 },
        axisLine: { lineStyle: { color: '#30363d' } },
        splitLine: { show: false },
        axisPointer: { label: { show: g === gridIdx - 1 } },
      });
      (yAxes as any[]).push({
        type: 'value',
        gridIndex: g,
        scale: true,
        splitLine: { lineStyle: { color: '#21262d' } },
        axisLabel: {
          color: '#8b949e',
          fontSize: 10,
          show: g !== stateGridIdx, // hide y-axis labels for state strip
        },
        axisLine: { show: false },
        axisTick: { show: false },
      });
    }

    // ── Series ──
    const series: any[] = [];

    // Candlestick data: [open, close, low, high]
    const candleData = [];
    for (let i = 0; i < len; i++) {
      candleData.push([
        windowedData.open[i],
        windowedData.close[i],
        windowedData.low[i],
        windowedData.high[i],
      ]);
    }
    series.push({
      name: 'Price',
      type: 'candlestick',
      data: candleData,
      xAxisIndex: priceGridIdx,
      yAxisIndex: priceGridIdx,
      itemStyle: {
        color: '#3fb950',        // up fill
        color0: '#f85149',       // down fill
        borderColor: '#3fb950',  // up border
        borderColor0: '#f85149', // down border
      },
    });

    // Price-scale feature overlays (on price grid)
    const priceFeatures = selectedFeatures.filter(isPriceScaleFeature);
    priceFeatures.forEach((featureKey) => {
      if (!featureData) return;
      const vals = featureData.features[featureKey];
      if (!vals) return;
      const aligned = alignToCategories(ts, featureData.timestamps, vals, NaN);
      const colorIdx = selectedFeatures.indexOf(featureKey);
      series.push({
        name: featureKey,
        type: 'line',
        data: aligned.map((v) => (isNaN(v) || !isFinite(v) ? null : v)),
        xAxisIndex: priceGridIdx,
        yAxisIndex: priceGridIdx,
        symbol: 'none',
        lineStyle: { width: 2, color: OVERLAY_COLORS[colorIdx % OVERLAY_COLORS.length] },
        itemStyle: { color: OVERLAY_COLORS[colorIdx % OVERLAY_COLORS.length] },
        connectNulls: false,
        z: 1,
      });
    });

    // Volume bars
    if (hasVolume && volumeGridIdx >= 0) {
      const volumeData = [];
      for (let i = 0; i < len; i++) {
        const isUp = windowedData.close[i] >= windowedData.open[i];
        volumeData.push({
          value: windowedData.volume[i],
          itemStyle: {
            color: isUp ? 'rgba(63, 185, 80, 0.5)' : 'rgba(248, 81, 73, 0.5)',
          },
        });
      }
      series.push({
        name: 'Volume',
        type: 'bar',
        data: volumeData,
        xAxisIndex: volumeGridIdx,
        yAxisIndex: volumeGridIdx,
        barWidth: '60%',
        large: true,
      });
    }

    // Regime state strip
    if (hasStates && stateGridIdx >= 0 && regimeData) {
      const stateIds = alignToCategories(ts, regimeData.timestamps, regimeData.state_ids, -1);
      const stateData = stateIds.map((sid) => {
        const info = regimeData.state_info[String(sid)];
        return {
          value: 1,
          itemStyle: { color: info?.color || '#6b7280' },
        };
      });
      series.push({
        name: 'Regime',
        type: 'bar',
        data: stateData,
        xAxisIndex: stateGridIdx,
        yAxisIndex: stateGridIdx,
        barWidth: '100%',
        barGap: '0%',
        barCategoryGap: '0%',
      });
      // Hide y-axis for state strip
      (yAxes as any[])[stateGridIdx].show = false;
    }

    // Cumulative PnL line
    if (hasPnl && pnlGridIdx >= 0 && pnlData) {
      const aligned = alignToCategories(ts, pnlData.timestamps, pnlData.cumulative_pnl, NaN);
      const pnlLineData = aligned.map((v) => (isNaN(v) || !isFinite(v) ? null : v));
      series.push({
        name: 'Cumulative PnL',
        type: 'line',
        data: pnlLineData,
        xAxisIndex: pnlGridIdx,
        yAxisIndex: pnlGridIdx,
        symbol: 'none',
        lineStyle: { width: 2, color: '#d29922' },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(210, 153, 34, 0.25)' },
              { offset: 1, color: 'rgba(210, 153, 34, 0.02)' },
            ],
          },
        },
        connectNulls: false,
        z: 2,
      });
      // Add a zero reference line via markLine
      series[series.length - 1].markLine = {
        silent: true,
        symbol: 'none',
        lineStyle: { color: '#484f58', type: 'dashed', width: 1 },
        data: [{ yAxis: 0 }],
        label: { show: false },
      };
    }

    // Non-price feature overlays (in indicator grid)
    if (hasIndicatorPane && indicatorGridIdx >= 0) {
      nonPriceFeatures.forEach((featureKey) => {
        if (!featureData) return;
        const vals = featureData.features[featureKey];
        if (!vals) return;
        const aligned = alignToCategories(ts, featureData.timestamps, vals, NaN);
        const colorIdx = selectedFeatures.indexOf(featureKey);
        series.push({
          name: featureKey,
          type: 'line',
          data: aligned.map((v) => (isNaN(v) || !isFinite(v) ? null : v)),
          xAxisIndex: indicatorGridIdx,
          yAxisIndex: indicatorGridIdx,
          symbol: 'none',
          lineStyle: { width: 2, color: OVERLAY_COLORS[colorIdx % OVERLAY_COLORS.length] },
          itemStyle: { color: OVERLAY_COLORS[colorIdx % OVERLAY_COLORS.length] },
          connectNulls: false,
        });
      });
    }

    // ── DataZoom (inside only, linked across all x-axes) ──
    const dataZoom: any[] = [
      {
        type: 'inside',
        xAxisIndex: allGridIndices,
        filterMode: 'filter',
        zoomOnMouseWheel: true,
        moveOnMouseMove: true,
        moveOnMouseWheel: false,
      },
    ];

    // ── Tooltip ──
    const tooltip: any = {
      trigger: 'axis',
      backgroundColor: 'rgba(13, 17, 23, 0.95)',
      borderColor: '#30363d',
      textStyle: { color: '#e6edf3', fontSize: 12 },
      axisPointer: {
        type: 'cross',
        crossStyle: { color: '#58a6ff' },
        lineStyle: { color: '#58a6ff', type: 'dashed' },
        label: {
          backgroundColor: '#388bfd',
        },
      },
      formatter: (params: any[]) => {
        if (!params || params.length === 0) return '';
        const idx = params[0].dataIndex;
        const isoTs = windowedData.timestamps[idx];
        if (!isoTs) return '';
        const d = new Date(isoTs);
        const header = `${estFullFmt.format(d)} EST`;
        let html = `<div style="font-weight:600;margin-bottom:4px">${header}</div>`;

        for (const p of params) {
          if (p.seriesName === 'Price' && p.data) {
            const [open, close, low, high] = p.data;
            const color = close >= open ? '#3fb950' : '#f85149';
            html += `<div style="color:${color}">O: ${open.toFixed(2)} H: ${high.toFixed(2)} L: ${low.toFixed(2)} C: ${close.toFixed(2)}</div>`;
          } else if (p.seriesName === 'Volume' && p.value != null) {
            const vol = typeof p.value === 'object' ? p.value.value : p.value;
            html += `<div style="color:#8b949e">Vol: ${Number(vol).toLocaleString()}</div>`;
          } else if (p.seriesName === 'Regime') {
            // skip in tooltip
          } else if (p.seriesName === 'Cumulative PnL') {
            const pnlVal = typeof p.value === 'object' ? p.value.value : p.value;
            if (pnlVal != null) {
              const pnlNum = Number(pnlVal);
              const pnlColor = pnlNum >= 0 ? '#3fb950' : '#f85149';
              const sign = pnlNum >= 0 ? '+' : '';
              html += `<div style="color:${pnlColor}">PnL: ${sign}$${pnlNum.toFixed(2)}</div>`;
            }
          } else if (p.value != null) {
            html += `<div><span style="color:${p.color}">\u25CF</span> ${p.seriesName}: ${Number(p.value).toFixed(4)}</div>`;
          }
        }
        return html;
      },
    };

    return {
      backgroundColor: '#0d1117',
      animation: false,
      grid: grids,
      xAxis: xAxes,
      yAxis: yAxes,
      series,
      dataZoom,
      tooltip,
    };
  }, [
    windowedData,
    categoryLabels,
    showVolume,
    showStates,
    regimeData,
    featureData,
    pnlData,
    selectedFeatures,
    height,
  ]);

  // ── Init ECharts instance + ResizeObserver ──
  useEffect(() => {
    if (!chartContainerRef.current) return;

    const instance = echarts.init(chartContainerRef.current, undefined, {
      renderer: 'canvas',
    });
    echartsRef.current = instance;

    const ro = new ResizeObserver(() => {
      instance.resize();
    });
    ro.observe(chartContainerRef.current);

    return () => {
      ro.disconnect();
      instance.dispose();
      echartsRef.current = null;
    };
  }, []);

  // ── Apply option when it changes ──
  useEffect(() => {
    if (!echartsRef.current || !chartOption) return;
    echartsRef.current.setOption(chartOption, { notMerge: true });
  }, [chartOption]);

  // ── Resize on height prop change ──
  useEffect(() => {
    if (!echartsRef.current || !chartContainerRef.current) return;
    chartContainerRef.current.style.height = `${height}px`;
    echartsRef.current.resize();
  }, [height]);

  // ── DataZoom change → onRangeChange callback ──
  useEffect(() => {
    if (!echartsRef.current || !onRangeChange || !windowedData) return;
    const instance = echartsRef.current;

    const handler = (params: any) => {
      // params.start / params.end are percentages (0–100)
      if (params.start != null && params.end != null) {
        const len = windowedData.timestamps.length;
        const from = Math.floor((params.start / 100) * len);
        const to = Math.ceil((params.end / 100) * len);
        onRangeChange(Math.max(0, from), Math.min(len, to));
      }
    };

    instance.on('datazoom', handler);
    return () => {
      instance.off('datazoom', handler);
    };
  }, [onRangeChange, windowedData]);

  // ── Fit / Reset handlers ──
  const handleFitContent = useCallback(() => {
    if (!echartsRef.current) return;
    echartsRef.current.dispatchAction({
      type: 'dataZoom',
      start: 0,
      end: 100,
    });
  }, []);

  const handleResetZoom = useCallback(() => {
    if (!echartsRef.current) return;
    echartsRef.current.dispatchAction({
      type: 'dataZoom',
      start: 0,
      end: 100,
    });
  }, []);

  return (
    <div style={{ position: 'relative' }}>
      <div
        ref={chartContainerRef}
        style={{
          width: '100%',
          height: `${height}px`,
          borderRadius: '8px',
          overflow: 'hidden',
        }}
      />
      {/* Chart controls */}
      <div
        style={{
          position: 'absolute',
          top: '8px',
          right: '8px',
          display: 'flex',
          gap: '4px',
          zIndex: 10,
        }}
      >
        <button
          onClick={handleFitContent}
          style={{
            padding: '4px 8px',
            fontSize: '11px',
            background: '#21262d',
            color: '#e6edf3',
            border: '1px solid #30363d',
            borderRadius: '4px',
            cursor: 'pointer',
          }}
          title="Fit all data"
        >
          Fit
        </button>
        <button
          onClick={handleResetZoom}
          style={{
            padding: '4px 8px',
            fontSize: '11px',
            background: '#21262d',
            color: '#e6edf3',
            border: '1px solid #30363d',
            borderRadius: '4px',
            cursor: 'pointer',
          }}
          title="Reset zoom"
        >
          Reset
        </button>
      </div>
      {/* Feature + PnL legend */}
      {(selectedFeatures.length > 0 || (pnlData && pnlData.cumulative_pnl.length > 0)) && (
        <div
          style={{
            position: 'absolute',
            top: '8px',
            left: '8px',
            display: 'flex',
            flexWrap: 'wrap',
            gap: '4px',
            zIndex: 10,
            maxWidth: '60%',
          }}
        >
          {pnlData && pnlData.cumulative_pnl.length > 0 && (
            <span
              style={{
                padding: '2px 6px',
                fontSize: '10px',
                background: 'rgba(0,0,0,0.7)',
                color: '#d29922',
                borderRadius: '3px',
                border: '1px solid #d29922',
              }}
            >
              Cumulative PnL
            </span>
          )}
          {selectedFeatures.map((feature, index) => {
            const color = OVERLAY_COLORS[index % OVERLAY_COLORS.length];
            return (
              <span
                key={feature}
                style={{
                  padding: '2px 6px',
                  fontSize: '10px',
                  background: 'rgba(0,0,0,0.7)',
                  color: color,
                  borderRadius: '3px',
                  border: `1px solid ${color}`,
                }}
              >
                {feature}
              </span>
            );
          })}
        </div>
      )}
      {/* State legend */}
      {showStates && regimeData && (
        <div
          style={{
            position: 'absolute',
            bottom: '8px',
            left: '8px',
            display: 'flex',
            flexWrap: 'wrap',
            gap: '4px',
            zIndex: 10,
            maxWidth: '80%',
          }}
        >
          {Object.entries(regimeData.state_info)
            .filter(([key]) => key !== '-1')
            .sort(([a], [b]) => Number(a) - Number(b))
            .map(([stateId, info]) => (
              <span
                key={stateId}
                style={{
                  padding: '2px 6px',
                  fontSize: '9px',
                  background: 'rgba(0,0,0,0.8)',
                  color: info.color,
                  borderRadius: '3px',
                  border: `1px solid ${info.color}`,
                }}
                title={info.description}
              >
                {info.short_label}
              </span>
            ))}
        </div>
      )}
    </div>
  );
}
