import { useEffect, useMemo } from 'react';
import * as echarts from 'echarts/core';
import { LineChart } from 'echarts/charts';
import { GridComponent, TooltipComponent, MarkLineComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import type { EChartsOption } from 'echarts';
import { useECharts } from './useECharts';
import { computeRollingSharpe } from '../../utils/dashboardMetrics';

echarts.use([LineChart, GridComponent, TooltipComponent, MarkLineComponent, CanvasRenderer]);

interface RollingSharpeChartProps {
  /** Daily P&L values (one per day) */
  dailyPnl: number[];
  /** Date labels corresponding to dailyPnl */
  dates: string[];
  height?: number;
}

export function RollingSharpeChart({ dailyPnl, dates, height = 220 }: RollingSharpeChartProps) {
  const { containerRef, setOption } = useECharts(height);

  const sharpe = useMemo(() => computeRollingSharpe(dailyPnl, 20), [dailyPnl]);

  const option = useMemo((): EChartsOption | null => {
    if (dates.length === 0) return null;

    // Clamp Infinity values for display
    const clampedSharpe = sharpe.map((v) => {
      if (v == null) return null;
      if (!isFinite(v)) return v > 0 ? 5 : -5;
      return Math.max(-5, Math.min(5, v));
    });

    return {
      backgroundColor: 'transparent',
      animation: false,
      grid: { left: 45, right: 16, top: 16, bottom: 28 },
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(13, 17, 23, 0.95)',
        borderColor: '#30363d',
        textStyle: { color: '#e6edf3', fontSize: 11 },
        formatter: (params: any) => {
          if (!Array.isArray(params) || !params[0]) return '';
          const idx = params[0].dataIndex;
          const val = clampedSharpe[idx];
          if (val == null) return `<div style="font-size:11px">${dates[idx]}</div><div>Insufficient data</div>`;
          const color = val >= 1 ? '#3fb950' : val >= 0.5 ? '#d29922' : '#f85149';
          return `<div style="font-size:11px">${dates[idx]}</div><div style="color:${color};font-weight:600">${val.toFixed(2)}</div>`;
        },
      },
      xAxis: {
        type: 'category',
        data: dates,
        axisLabel: { color: '#8b949e', fontSize: 9, interval: 'auto' },
        axisTick: { show: false },
        axisLine: { lineStyle: { color: '#30363d' } },
      },
      yAxis: {
        type: 'value',
        splitLine: { lineStyle: { color: '#21262d' } },
        axisLabel: { color: '#8b949e', fontSize: 9 },
        axisLine: { show: false },
        axisTick: { show: false },
      },
      series: [{
        type: 'line',
        data: clampedSharpe,
        symbol: 'none',
        lineStyle: { width: 1.5, color: '#58a6ff' },
        itemStyle: { color: '#58a6ff' },
        connectNulls: false,
        markLine: {
          silent: true,
          symbol: 'none',
          lineStyle: { type: 'dashed', width: 1 },
          data: [
            { yAxis: 1, lineStyle: { color: '#3fb950' }, label: { show: true, formatter: 'Sharpe = 1', color: '#3fb950', fontSize: 9, position: 'insideEndTop' } },
            { yAxis: 0, lineStyle: { color: '#484f58' }, label: { show: false } },
          ],
        },
      }],
    };
  }, [dates, sharpe]);

  useEffect(() => {
    if (option) setOption(option);
  }, [option, setOption]);

  return (
    <div
      ref={containerRef}
      style={{ width: '100%', height: `${height}px`, borderRadius: '6px', overflow: 'hidden' }}
    />
  );
}
