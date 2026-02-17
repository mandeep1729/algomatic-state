import { useEffect, useMemo } from 'react';
import * as echarts from 'echarts/core';
import { HeatmapChart } from 'echarts/charts';
import { GridComponent, TooltipComponent, VisualMapComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import type { EChartsOption } from 'echarts';
import { useECharts } from './useECharts';
import type { TimingInsight } from '../../types';

echarts.use([HeatmapChart, GridComponent, TooltipComponent, VisualMapComponent, CanvasRenderer]);

interface TimeOfDayHeatmapChartProps {
  timingData: TimingInsight[];
  height?: number;
}

export function TimeOfDayHeatmapChart({ timingData, height = 200 }: TimeOfDayHeatmapChartProps) {
  const { containerRef, setOption } = useECharts(height);

  const option = useMemo((): EChartsOption | null => {
    if (timingData.length === 0) return null;

    // Build heatmap data: [hourIndex, dayIndex, tradeCount]
    // Since timing data only has hour_of_day, we distribute across days evenly
    const hours = timingData.map((t) => `${t.hour_of_day}:00`);
    const maxCount = Math.max(...timingData.map((t) => t.trade_count), 1);

    // For a single-row heatmap (hour_of_day only, no day breakdown)
    const data = timingData.map((t, i) => [i, 0, t.trade_count]);

    return {
      backgroundColor: 'transparent',
      animation: false,
      grid: { left: 40, right: 16, top: 8, bottom: 48 },
      tooltip: {
        trigger: 'item',
        backgroundColor: 'rgba(13, 17, 23, 0.95)',
        borderColor: '#30363d',
        textStyle: { color: '#e6edf3', fontSize: 11 },
        formatter: (params: any) => {
          const idx = params.value[0];
          const t = timingData[idx];
          if (!t) return '';
          const scoreColor = t.avg_score >= 70 ? '#3fb950' : t.avg_score >= 50 ? '#d29922' : '#f85149';
          return `<div style="font-weight:600">${t.hour_of_day}:00 EST</div>`
            + `<div>${t.trade_count} trades</div>`
            + `<div style="color:${scoreColor}">Avg Score: ${t.avg_score}</div>`
            + `<div>Flagged: ${t.flagged_pct.toFixed(0)}%</div>`;
        },
      },
      xAxis: {
        type: 'category',
        data: hours,
        axisLabel: { color: '#8b949e', fontSize: 9 },
        axisTick: { show: false },
        axisLine: { lineStyle: { color: '#30363d' } },
        splitArea: { show: true, areaStyle: { color: ['transparent', 'rgba(255,255,255,0.02)'] } },
      },
      yAxis: {
        type: 'category',
        data: ['Trades'],
        axisLabel: { color: '#8b949e', fontSize: 9 },
        axisTick: { show: false },
        axisLine: { show: false },
      },
      visualMap: {
        min: 0,
        max: maxCount,
        calculable: false,
        orient: 'horizontal',
        left: 'center',
        bottom: 2,
        itemWidth: 12,
        itemHeight: 100,
        textStyle: { color: '#8b949e', fontSize: 9 },
        inRange: {
          color: ['#0d1117', '#1a3a2a', '#238636', '#3fb950'],
        },
      },
      series: [{
        type: 'heatmap',
        data,
        label: {
          show: true,
          color: '#e6edf3',
          fontSize: 9,
          formatter: (params: any) => {
            const count = params.value[2];
            return count > 0 ? `${count}` : '';
          },
        },
        itemStyle: {
          borderColor: '#0d1117',
          borderWidth: 2,
          borderRadius: 3,
        },
      }],
    };
  }, [timingData]);

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
