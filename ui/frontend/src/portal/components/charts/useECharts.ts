import { useEffect, useRef, useCallback } from 'react';
import * as echarts from 'echarts/core';
import type { EChartsOption } from 'echarts';

type EChartsInstance = ReturnType<typeof echarts.init>;

/**
 * Shared hook for ECharts lifecycle management.
 *
 * Handles init, ResizeObserver, setOption, height changes, and dispose.
 * Each chart component registers its own ECharts modules at module level
 * and calls this hook for the boilerplate lifecycle.
 */
export function useECharts(height: number = 300) {
  const containerRef = useRef<HTMLDivElement>(null);
  const instanceRef = useRef<EChartsInstance | null>(null);

  // Init instance + ResizeObserver
  useEffect(() => {
    if (!containerRef.current) return;

    const instance = echarts.init(containerRef.current, undefined, {
      renderer: 'canvas',
    });
    instanceRef.current = instance;

    const ro = new ResizeObserver(() => {
      instance.resize();
    });
    ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      instance.dispose();
      instanceRef.current = null;
    };
  }, []);

  // Resize on height prop change
  useEffect(() => {
    if (!instanceRef.current || !containerRef.current) return;
    containerRef.current.style.height = `${height}px`;
    instanceRef.current.resize();
  }, [height]);

  // Stable setOption wrapper
  const setOption = useCallback((option: EChartsOption) => {
    if (!instanceRef.current) return;
    instanceRef.current.setOption(option, { notMerge: true });
  }, []);

  return { containerRef, setOption };
}
