import { useEffect, useRef, useMemo } from 'react';
import * as echarts from 'echarts/core';
import { LineChart } from 'echarts/charts';
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  MarkLineComponent,
} from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import type { EChartsOption } from 'echarts';

type EChartsInstance = ReturnType<typeof echarts.init>;

// Register only what we need for tree-shaking
echarts.use([
  LineChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  MarkLineComponent,
  CanvasRenderer,
]);

interface CampaignPricePnlChartProps {
  priceTimestamps: string[];
  closePrices: number[];
  pnlTimestamps: string[];
  cumulativePnl: number[];
  height?: number;
}

/** EST time formatter for tooltip. */
const estFullFmt = new Intl.DateTimeFormat('en-US', {
  timeZone: 'America/New_York',
  month: 'short',
  day: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
});

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

/** Format an ISO timestamp to a short EST label for the x-axis. */
function formatTimestampEST(iso: string): string {
  const d = new Date(iso);
  return `${estDateFmt.format(d)} ${estTimeFmt.format(d)}`;
}

/**
 * Align PnL values to the price category axis.
 * Returns an array of values (or null for gaps) indexed by the category axis.
 */
function alignToCategories(
  categoryTimestamps: string[],
  sourceTimestamps: string[],
  sourceValues: number[],
): (number | null)[] {
  const map = new Map<string, number>();
  for (let i = 0; i < sourceTimestamps.length; i++) {
    map.set(sourceTimestamps[i], sourceValues[i]);
  }
  return categoryTimestamps.map((ts) => {
    const val = map.get(ts);
    return val != null && isFinite(val) ? val : null;
  });
}

/**
 * Compact dual-axis chart showing ticker close price (left Y-axis) and
 * campaign cumulative PnL (right Y-axis) overlaid on a shared time axis.
 */
export function CampaignPricePnlChart({
  priceTimestamps,
  closePrices,
  pnlTimestamps,
  cumulativePnl,
  height = 220,
}: CampaignPricePnlChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const echartsRef = useRef<EChartsInstance | null>(null);

  // Category labels for the x-axis
  const categoryLabels = useMemo(
    () => priceTimestamps.map(formatTimestampEST),
    [priceTimestamps],
  );

  // Align PnL data to the price timestamps
  const alignedPnl = useMemo(
    () => alignToCategories(priceTimestamps, pnlTimestamps, cumulativePnl),
    [priceTimestamps, pnlTimestamps, cumulativePnl],
  );

  // Build ECharts option
  const chartOption = useMemo((): EChartsOption | null => {
    if (closePrices.length === 0) return null;

    // Determine PnL color from the final value
    const lastPnl = cumulativePnl.length > 0
      ? cumulativePnl[cumulativePnl.length - 1]
      : 0;
    const pnlColor = lastPnl >= 0 ? '#3fb950' : '#f85149';
    const pnlAreaColor = lastPnl >= 0
      ? 'rgba(63, 185, 80, 0.12)'
      : 'rgba(248, 81, 73, 0.12)';

    return {
      backgroundColor: 'transparent',
      animation: false,
      legend: {
        show: true,
        top: 4,
        right: 8,
        textStyle: { color: '#8b949e', fontSize: 10 },
        itemWidth: 14,
        itemHeight: 2,
        itemGap: 12,
      },
      grid: {
        left: 50,
        right: 50,
        top: 28,
        bottom: 24,
      },
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(13, 17, 23, 0.95)',
        borderColor: '#30363d',
        textStyle: { color: '#e6edf3', fontSize: 11 },
        axisPointer: {
          type: 'line',
          lineStyle: { color: '#58a6ff', type: 'dashed' },
        },
        formatter: (params: any) => {
          if (!Array.isArray(params) || params.length === 0) return '';
          const idx = params[0].dataIndex;
          const isoTs = priceTimestamps[idx];
          if (!isoTs) return '';
          const d = new Date(isoTs);
          const header = `${estFullFmt.format(d)} EST`;
          let html = `<div style="font-weight:600;margin-bottom:4px;font-size:11px">${header}</div>`;

          for (const p of params) {
            if (p.seriesName === 'Price' && p.value != null) {
              html += `<div style="color:#58a6ff">Price: $${Number(p.value).toFixed(2)}</div>`;
            } else if (p.seriesName === 'Cumulative PnL' && p.value != null) {
              const pnlVal = Number(p.value);
              const color = pnlVal >= 0 ? '#3fb950' : '#f85149';
              const sign = pnlVal >= 0 ? '+' : '';
              html += `<div style="color:${color}">PnL: ${sign}$${pnlVal.toFixed(2)}</div>`;
            }
          }
          return html;
        },
      },
      xAxis: {
        type: 'category',
        data: categoryLabels,
        axisLabel: {
          color: '#8b949e',
          fontSize: 9,
          rotate: 0,
          interval: 'auto',
        },
        axisTick: { show: false },
        axisLine: { lineStyle: { color: '#30363d' } },
        splitLine: { show: false },
      },
      yAxis: [
        {
          // Left Y-axis: Price
          type: 'value',
          position: 'left',
          scale: true,
          splitLine: { lineStyle: { color: '#21262d' } },
          axisLabel: {
            color: '#58a6ff',
            fontSize: 9,
            formatter: (val: number) => `$${val.toFixed(0)}`,
          },
          axisLine: { show: false },
          axisTick: { show: false },
        },
        {
          // Right Y-axis: PnL
          type: 'value',
          position: 'right',
          scale: true,
          splitLine: { show: false },
          axisLabel: {
            color: pnlColor,
            fontSize: 9,
            formatter: (val: number) => {
              const sign = val >= 0 ? '+' : '';
              return `${sign}$${val.toFixed(0)}`;
            },
          },
          axisLine: { show: false },
          axisTick: { show: false },
        },
      ],
      series: [
        {
          name: 'Price',
          type: 'line',
          data: closePrices.map((v) => (isFinite(v) ? v : null)),
          yAxisIndex: 0,
          symbol: 'none',
          lineStyle: { width: 1.5, color: '#58a6ff' },
          itemStyle: { color: '#58a6ff' },
          connectNulls: false,
          z: 2,
        },
        {
          name: 'Cumulative PnL',
          type: 'line',
          data: alignedPnl,
          yAxisIndex: 1,
          symbol: 'none',
          lineStyle: { width: 1.5, color: pnlColor },
          itemStyle: { color: pnlColor },
          areaStyle: {
            color: pnlAreaColor,
          },
          connectNulls: false,
          z: 1,
          markLine: {
            silent: true,
            symbol: 'none',
            lineStyle: { color: '#484f58', type: 'dashed', width: 1 },
            data: [{ yAxis: 0 }],
            label: { show: false },
          },
        },
      ],
    };
  }, [closePrices, alignedPnl, categoryLabels, priceTimestamps, cumulativePnl]);

  // Init ECharts instance + ResizeObserver
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

  // Apply option when it changes
  useEffect(() => {
    if (!echartsRef.current || !chartOption) return;
    echartsRef.current.setOption(chartOption, { notMerge: true });
  }, [chartOption]);

  // Resize on height prop change
  useEffect(() => {
    if (!echartsRef.current || !chartContainerRef.current) return;
    chartContainerRef.current.style.height = `${height}px`;
    echartsRef.current.resize();
  }, [height]);

  return (
    <div
      ref={chartContainerRef}
      style={{
        width: '100%',
        height: `${height}px`,
        borderRadius: '6px',
        overflow: 'hidden',
      }}
    />
  );
}
