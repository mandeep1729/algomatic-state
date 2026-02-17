import { useEffect, useMemo } from 'react';
import * as echarts from 'echarts/core';
import { LineChart } from 'echarts/charts';
import { GridComponent, TooltipComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import type { EChartsOption } from 'echarts';
import { useECharts } from './useECharts';
import { computeDrawdown } from '../../utils/dashboardMetrics';

echarts.use([LineChart, GridComponent, TooltipComponent, CanvasRenderer]);

interface DrawdownChartProps {
  timestamps: string[];
  cumulativePnl: number[];
  height?: number;
}

export function DrawdownChart({ timestamps, cumulativePnl, height = 220 }: DrawdownChartProps) {
  const { containerRef, setOption } = useECharts(height);

  const drawdown = useMemo(() => computeDrawdown(cumulativePnl), [cumulativePnl]);

  const option = useMemo((): EChartsOption | null => {
    if (timestamps.length === 0) return null;
    return {
      backgroundColor: 'transparent',
      animation: false,
      grid: { left: 55, right: 16, top: 16, bottom: 28 },
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(13, 17, 23, 0.95)',
        borderColor: '#30363d',
        textStyle: { color: '#e6edf3', fontSize: 11 },
        formatter: (params: any) => {
          if (!Array.isArray(params) || !params[0]) return '';
          const idx = params[0].dataIndex;
          const val = drawdown[idx];
          return `<div style="font-size:11px">${timestamps[idx]}</div><div style="color:#f85149;font-weight:600">$${val.toFixed(2)}</div>`;
        },
      },
      xAxis: {
        type: 'category',
        data: timestamps,
        axisLabel: { color: '#8b949e', fontSize: 9, interval: 'auto' },
        axisTick: { show: false },
        axisLine: { lineStyle: { color: '#30363d' } },
      },
      yAxis: {
        type: 'value',
        max: 0,
        splitLine: { lineStyle: { color: '#21262d' } },
        axisLabel: {
          color: '#8b949e',
          fontSize: 9,
          formatter: (val: number) => `$${val.toFixed(0)}`,
        },
        axisLine: { show: false },
        axisTick: { show: false },
      },
      series: [{
        type: 'line',
        data: drawdown,
        symbol: 'none',
        lineStyle: { width: 1.5, color: '#f85149' },
        itemStyle: { color: '#f85149' },
        areaStyle: { color: 'rgba(248, 81, 73, 0.15)' },
      }],
    };
  }, [timestamps, drawdown]);

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
