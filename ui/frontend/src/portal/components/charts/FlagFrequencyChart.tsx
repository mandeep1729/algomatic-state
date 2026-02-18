/**
 * FlagFrequencyChart — horizontal bar chart showing flag occurrences,
 * colored by the average PnL impact of trades with that flag.
 */

import { useEffect, useMemo, useCallback } from 'react';
import * as echarts from 'echarts/core';
import { BarChart } from 'echarts/charts';
import { GridComponent, TooltipComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import type { EChartsOption } from 'echarts';
import { useECharts } from './useECharts';

echarts.use([BarChart, GridComponent, TooltipComponent, CanvasRenderer]);

export interface FlagData {
  flag: string;
  count: number;
  avgPnl: number;
}

interface FlagFrequencyChartProps {
  data: FlagData[];
  height?: number;
  onBarClick?: (flag: string) => void;
}

export function FlagFrequencyChart({ data, height = 260, onBarClick }: FlagFrequencyChartProps) {
  const { containerRef, setOption } = useECharts(height);

  const sorted = useMemo(
    () => [...data].sort((a, b) => b.count - a.count),
    [data],
  );

  const option = useMemo((): EChartsOption | null => {
    if (sorted.length === 0) return null;

    return {
      backgroundColor: 'transparent',
      animation: false,
      grid: { left: 120, right: 24, top: 16, bottom: 28 },
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(13, 17, 23, 0.95)',
        borderColor: '#30363d',
        textStyle: { color: '#e6edf3', fontSize: 11 },
        formatter: (params: any) => {
          if (!Array.isArray(params) || !params[0]) return '';
          const idx = params[0].dataIndex;
          const item = sorted[idx];
          const sign = item.avgPnl >= 0 ? '+' : '';
          const color = item.avgPnl >= 0 ? '#3fb950' : '#f85149';
          return `<div style="font-size:11px;font-weight:600">${item.flag}</div>
            <div>${item.count} occurrence${item.count !== 1 ? 's' : ''}</div>
            <div style="color:${color}">Avg P&L: ${sign}$${item.avgPnl.toFixed(2)}</div>`;
        },
      },
      yAxis: {
        type: 'category',
        data: sorted.map((d) => d.flag),
        axisLabel: {
          color: '#8b949e',
          fontSize: 10,
          width: 100,
          overflow: 'truncate',
        },
        axisTick: { show: false },
        axisLine: { lineStyle: { color: '#30363d' } },
        inverse: true,
      },
      xAxis: {
        type: 'value',
        splitLine: { lineStyle: { color: '#21262d' } },
        axisLabel: { color: '#8b949e', fontSize: 9 },
        axisLine: { show: false },
        axisTick: { show: false },
      },
      series: [{
        type: 'bar',
        data: sorted.map((d) => ({
          value: d.count,
          itemStyle: {
            color: d.avgPnl >= 0
              ? 'rgba(63, 185, 80, 0.6)'
              : 'rgba(248, 81, 73, 0.6)',
            borderRadius: [0, 3, 3, 0],
          },
        })),
        barMaxWidth: 24,
      }],
    };
  }, [sorted]);

  useEffect(() => {
    if (option) setOption(option);
  }, [option, setOption]);

  const handleClick = useCallback(() => {
    if (!containerRef.current || !onBarClick) return;
    const instance = echarts.getInstanceByDom(containerRef.current);
    if (!instance) return;

    instance.off('click');
    instance.on('click', (params: any) => {
      if (params.componentType === 'series' && params.dataIndex != null) {
        onBarClick(sorted[params.dataIndex]?.flag);
      }
    });
  }, [containerRef, onBarClick, sorted]);

  useEffect(() => {
    const timer = setTimeout(handleClick, 50);
    return () => clearTimeout(timer);
  }, [handleClick]);

  return (
    <div
      ref={containerRef}
      style={{ width: '100%', height: `${height}px`, borderRadius: '6px', overflow: 'hidden', cursor: onBarClick ? 'pointer' : 'default' }}
    />
  );
}
