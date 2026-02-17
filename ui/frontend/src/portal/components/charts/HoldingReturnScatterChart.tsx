import { useEffect, useMemo } from 'react';
import * as echarts from 'echarts/core';
import { ScatterChart } from 'echarts/charts';
import { GridComponent, TooltipComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import type { EChartsOption } from 'echarts';
import { useECharts } from './useECharts';
import { formatDuration } from '../../utils/dashboardMetrics';

echarts.use([ScatterChart, GridComponent, TooltipComponent, CanvasRenderer]);

export interface ScatterPoint {
  holdingMinutes: number;
  returnDollars: number;
  symbol?: string;
}

interface HoldingReturnScatterChartProps {
  points: ScatterPoint[];
  height?: number;
}

export function HoldingReturnScatterChart({ points, height = 220 }: HoldingReturnScatterChartProps) {
  const { containerRef, setOption } = useECharts(height);

  const option = useMemo((): EChartsOption | null => {
    if (points.length === 0) return null;

    return {
      backgroundColor: 'transparent',
      animation: false,
      grid: { left: 55, right: 16, top: 16, bottom: 36 },
      tooltip: {
        trigger: 'item',
        backgroundColor: 'rgba(13, 17, 23, 0.95)',
        borderColor: '#30363d',
        textStyle: { color: '#e6edf3', fontSize: 11 },
        formatter: (params: any) => {
          const [mins, ret] = params.value;
          const pt = points[params.dataIndex];
          const color = ret >= 0 ? '#3fb950' : '#f85149';
          const sign = ret >= 0 ? '+' : '';
          let html = pt?.symbol ? `<div style="font-weight:600">${pt.symbol}</div>` : '';
          html += `<div>Held: ${formatDuration(mins)}</div>`;
          html += `<div style="color:${color}">Return: ${sign}$${ret.toFixed(2)}</div>`;
          return html;
        },
      },
      xAxis: {
        type: 'value',
        name: 'Holding Period',
        nameLocation: 'center',
        nameGap: 22,
        nameTextStyle: { color: '#8b949e', fontSize: 10 },
        splitLine: { lineStyle: { color: '#21262d' } },
        axisLabel: {
          color: '#8b949e',
          fontSize: 9,
          formatter: (val: number) => formatDuration(val),
        },
        axisLine: { lineStyle: { color: '#30363d' } },
        axisTick: { show: false },
      },
      yAxis: {
        type: 'value',
        name: 'Return ($)',
        nameLocation: 'center',
        nameGap: 42,
        nameTextStyle: { color: '#8b949e', fontSize: 10 },
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
        type: 'scatter',
        symbolSize: 8,
        data: points.map((p) => ({
          value: [p.holdingMinutes, p.returnDollars],
          itemStyle: {
            color: p.returnDollars >= 0 ? 'rgba(63, 185, 80, 0.7)' : 'rgba(248, 81, 73, 0.7)',
          },
        })),
      }],
    };
  }, [points]);

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
