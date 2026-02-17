import { useEffect, useMemo } from 'react';
import * as echarts from 'echarts/core';
import { LineChart } from 'echarts/charts';
import { GridComponent, TooltipComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import type { EChartsOption } from 'echarts';
import { useECharts } from './useECharts';

echarts.use([LineChart, GridComponent, TooltipComponent, CanvasRenderer]);

interface EquityCurveChartProps {
  timestamps: string[];
  cumulativePnl: number[];
  height?: number;
}

export function EquityCurveChart({ timestamps, cumulativePnl, height = 260 }: EquityCurveChartProps) {
  const { containerRef, setOption } = useECharts(height);

  const option = useMemo((): EChartsOption | null => {
    if (timestamps.length === 0) return null;
    const lastVal = cumulativePnl[cumulativePnl.length - 1] ?? 0;
    const color = lastVal >= 0 ? '#3fb950' : '#f85149';
    const areaColor = lastVal >= 0 ? 'rgba(63, 185, 80, 0.15)' : 'rgba(248, 81, 73, 0.15)';

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
          const val = cumulativePnl[idx];
          const sign = val >= 0 ? '+' : '';
          return `<div style="font-size:11px">${timestamps[idx]}</div><div style="color:${color};font-weight:600">${sign}$${val.toFixed(2)}</div>`;
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
        scale: true,
        splitLine: { lineStyle: { color: '#21262d' } },
        axisLabel: {
          color: '#8b949e',
          fontSize: 9,
          formatter: (val: number) => {
            const sign = val >= 0 ? '+' : '';
            return `${sign}$${val.toFixed(0)}`;
          },
        },
        axisLine: { show: false },
        axisTick: { show: false },
      },
      series: [{
        type: 'line',
        data: cumulativePnl,
        symbol: 'none',
        lineStyle: { width: 1.5, color },
        itemStyle: { color },
        areaStyle: { color: areaColor },
      }],
    };
  }, [timestamps, cumulativePnl]);

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
