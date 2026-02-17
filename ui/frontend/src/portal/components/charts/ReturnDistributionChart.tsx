import { useEffect, useMemo } from 'react';
import * as echarts from 'echarts/core';
import { BarChart } from 'echarts/charts';
import { GridComponent, TooltipComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import type { EChartsOption } from 'echarts';
import { useECharts } from './useECharts';
import { buildHistogramBins } from '../../utils/dashboardMetrics';

echarts.use([BarChart, GridComponent, TooltipComponent, CanvasRenderer]);

interface ReturnDistributionChartProps {
  /** Array of return values (dollar amounts) */
  returns: number[];
  height?: number;
}

export function ReturnDistributionChart({ returns, height = 220 }: ReturnDistributionChartProps) {
  const { containerRef, setOption } = useECharts(height);

  const bins = useMemo(() => buildHistogramBins(returns, 20), [returns]);

  const option = useMemo((): EChartsOption | null => {
    if (bins.length === 0) return null;

    const colors = bins.map((b) => {
      const midpoint = (b.min + b.max) / 2;
      return midpoint >= 0 ? '#3fb950' : '#f85149';
    });

    return {
      backgroundColor: 'transparent',
      animation: false,
      grid: { left: 40, right: 16, top: 16, bottom: 28 },
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(13, 17, 23, 0.95)',
        borderColor: '#30363d',
        textStyle: { color: '#e6edf3', fontSize: 11 },
        formatter: (params: any) => {
          if (!Array.isArray(params) || !params[0]) return '';
          const idx = params[0].dataIndex;
          const bin = bins[idx];
          return `<div style="font-size:11px">$${bin.min.toFixed(0)} to $${bin.max.toFixed(0)}</div><div style="font-weight:600">${bin.count} trades</div>`;
        },
      },
      xAxis: {
        type: 'category',
        data: bins.map((b) => b.label),
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
        type: 'bar',
        data: bins.map((b, i) => ({
          value: b.count,
          itemStyle: { color: colors[i] },
        })),
        barWidth: '80%',
      }],
    };
  }, [bins]);

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
