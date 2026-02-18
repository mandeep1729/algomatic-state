/**
 * PnlByGroupChart — ECharts bar chart showing P&L grouped by a dimension.
 * Bars are colored green (profit) / red (loss).
 * Clicking a bar fires onBarClick with the group key.
 */

import { useEffect, useMemo, useCallback } from 'react';
import * as echarts from 'echarts/core';
import { BarChart } from 'echarts/charts';
import { GridComponent, TooltipComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import type { EChartsOption } from 'echarts';
import { useECharts } from './useECharts';

echarts.use([BarChart, GridComponent, TooltipComponent, CanvasRenderer]);

export interface GroupedPnl {
  key: string;
  totalPnl: number;
  tradeCount: number;
}

interface PnlByGroupChartProps {
  data: GroupedPnl[];
  height?: number;
  onBarClick?: (key: string) => void;
}

export function PnlByGroupChart({ data, height = 260, onBarClick }: PnlByGroupChartProps) {
  const { containerRef, setOption } = useECharts(height);

  const sorted = useMemo(
    () => [...data].sort((a, b) => a.totalPnl - b.totalPnl),
    [data],
  );

  const option = useMemo((): EChartsOption | null => {
    if (sorted.length === 0) return null;

    return {
      backgroundColor: 'transparent',
      animation: false,
      grid: { left: 60, right: 16, top: 16, bottom: 32 },
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(13, 17, 23, 0.95)',
        borderColor: '#30363d',
        textStyle: { color: '#e6edf3', fontSize: 11 },
        formatter: (params: any) => {
          if (!Array.isArray(params) || !params[0]) return '';
          const idx = params[0].dataIndex;
          const item = sorted[idx];
          const sign = item.totalPnl >= 0 ? '+' : '';
          const color = item.totalPnl >= 0 ? '#3fb950' : '#f85149';
          return `<div style="font-size:11px;font-weight:600">${item.key}</div>
            <div style="color:${color}">${sign}$${item.totalPnl.toFixed(2)}</div>
            <div style="font-size:10px;color:#8b949e">${item.tradeCount} trade${item.tradeCount !== 1 ? 's' : ''}</div>`;
        },
      },
      xAxis: {
        type: 'category',
        data: sorted.map((d) => d.key),
        axisLabel: {
          color: '#8b949e',
          fontSize: 9,
          interval: 0,
          rotate: sorted.length > 8 ? 45 : 0,
        },
        axisTick: { show: false },
        axisLine: { lineStyle: { color: '#30363d' } },
      },
      yAxis: {
        type: 'value',
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
        type: 'bar',
        data: sorted.map((d) => ({
          value: d.totalPnl,
          itemStyle: {
            color: d.totalPnl >= 0 ? '#3fb950' : '#f85149',
            borderRadius: [2, 2, 0, 0],
          },
        })),
        barMaxWidth: 40,
      }],
    };
  }, [sorted]);

  useEffect(() => {
    if (option) setOption(option);
  }, [option, setOption]);

  // Click handler - attach to the ECharts instance via containerRef
  const handleClick = useCallback(() => {
    if (!containerRef.current || !onBarClick) return;
    const instance = echarts.getInstanceByDom(containerRef.current);
    if (!instance) return;

    instance.off('click');
    instance.on('click', (params: any) => {
      if (params.componentType === 'series' && params.dataIndex != null) {
        onBarClick(sorted[params.dataIndex]?.key);
      }
    });
  }, [containerRef, onBarClick, sorted]);

  useEffect(() => {
    // Small delay to ensure instance is ready after setOption
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
