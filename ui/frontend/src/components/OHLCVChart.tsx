import { useEffect, useRef, useCallback } from 'react';
import {
  createChart,
  IChartApi,
  ISeriesApi,
  CandlestickData,
  HistogramData,
  Time,
  ColorType,
  CrosshairMode,
} from 'lightweight-charts';

interface OHLCVData {
  timestamps: string[];
  open: number[];
  high: number[];
  low: number[];
  close: number[];
  volume: number[];
}

interface OHLCVChartProps {
  data: OHLCVData | null;
  showVolume?: boolean;
  height?: number;
  onRangeChange?: (start: number, end: number) => void;
}

// Convert ISO timestamp to Unix timestamp (seconds)
const toUnixTime = (isoString: string): Time => {
  return Math.floor(new Date(isoString).getTime() / 1000) as Time;
};

export function OHLCVChart({
  data,
  showVolume = true,
  height = 500,
  onRangeChange,
}: OHLCVChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candlestickSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<'Histogram'> | null>(null);

  // Initialize chart
  useEffect(() => {
    if (!chartContainerRef.current) return;

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: '#0d1117' },
        textColor: '#e6edf3',
      },
      grid: {
        vertLines: { color: '#21262d' },
        horzLines: { color: '#21262d' },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: {
          color: '#58a6ff',
          width: 1,
          style: 2,
          labelBackgroundColor: '#388bfd',
        },
        horzLine: {
          color: '#58a6ff',
          width: 1,
          style: 2,
          labelBackgroundColor: '#388bfd',
        },
      },
      rightPriceScale: {
        borderColor: '#30363d',
        scaleMargins: {
          top: 0.1,
          bottom: 0.2,
        },
      },
      timeScale: {
        borderColor: '#30363d',
        timeVisible: true,
        secondsVisible: false,
        fixLeftEdge: true,
        fixRightEdge: true,
        tickMarkFormatter: (time: number, tickMarkType: number) => {
          const date = new Date(time * 1000);
          const day = date.getDate();
          const hours = date.getHours().toString().padStart(2, '0');
          const minutes = date.getMinutes().toString().padStart(2, '0');
          const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
          // tickMarkType: 0=Year, 1=Month, 2=DayOfMonth, 3=Time, 4=TimeWithSeconds
          if (tickMarkType <= 2) {
            return `${months[date.getMonth()]} ${day}`;
          }
          return `${hours}:${minutes}`;
        },
      },
      handleScroll: {
        vertTouchDrag: false,
      },
    });

    chart.timeScale().fitContent();

    // Add candlestick series
    const candlestickSeries = chart.addCandlestickSeries({
      upColor: '#3fb950',
      downColor: '#f85149',
      borderUpColor: '#3fb950',
      borderDownColor: '#f85149',
      wickUpColor: '#3fb950',
      wickDownColor: '#f85149',
    });

    // Add volume series as histogram at bottom
    const volumeSeries = chart.addHistogramSeries({
      priceFormat: {
        type: 'volume',
      },
      priceScaleId: 'volume',
    });

    // Configure volume scale
    chart.priceScale('volume').applyOptions({
      scaleMargins: {
        top: 0.85,
        bottom: 0,
      },
    });

    chartRef.current = chart;
    candlestickSeriesRef.current = candlestickSeries;
    volumeSeriesRef.current = volumeSeries;

    // Handle visible range change
    chart.timeScale().subscribeVisibleLogicalRangeChange((logicalRange) => {
      if (logicalRange && onRangeChange && data) {
        const from = Math.max(0, Math.floor(logicalRange.from));
        const to = Math.min(data.timestamps.length, Math.ceil(logicalRange.to));
        onRangeChange(from, to);
      }
    });

    // Handle resize
    const handleResize = () => {
      if (chartContainerRef.current) {
        chart.applyOptions({
          width: chartContainerRef.current.clientWidth,
        });
      }
    };

    window.addEventListener('resize', handleResize);
    handleResize();

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
      chartRef.current = null;
      candlestickSeriesRef.current = null;
      volumeSeriesRef.current = null;
    };
  }, []);

  // Update chart data
  useEffect(() => {
    if (!data || !candlestickSeriesRef.current || !volumeSeriesRef.current) {
      return;
    }

    // Prepare candlestick data
    const candlestickData: CandlestickData[] = data.timestamps.map((ts, i) => ({
      time: toUnixTime(ts),
      open: data.open[i],
      high: data.high[i],
      low: data.low[i],
      close: data.close[i],
    }));

    // Prepare volume data with colors based on candle direction
    const volumeData: HistogramData[] = data.timestamps.map((ts, i) => {
      const isUp = i === 0 || data.close[i] >= data.open[i];
      return {
        time: toUnixTime(ts),
        value: data.volume[i],
        color: isUp ? 'rgba(63, 185, 80, 0.5)' : 'rgba(248, 81, 73, 0.5)',
      };
    });

    candlestickSeriesRef.current.setData(candlestickData);
    volumeSeriesRef.current.setData(volumeData);

    // Fit content to show all data
    if (chartRef.current) {
      chartRef.current.timeScale().fitContent();
    }
  }, [data]);

  // Update volume visibility
  useEffect(() => {
    if (volumeSeriesRef.current) {
      volumeSeriesRef.current.applyOptions({
        visible: showVolume,
      });
    }
  }, [showVolume]);

  // Update chart height
  useEffect(() => {
    if (chartRef.current) {
      chartRef.current.applyOptions({ height });
    }
  }, [height]);

  const handleFitContent = useCallback(() => {
    if (chartRef.current) {
      chartRef.current.timeScale().fitContent();
    }
  }, []);

  const handleResetZoom = useCallback(() => {
    if (chartRef.current) {
      chartRef.current.timeScale().resetTimeScale();
      chartRef.current.priceScale('right').applyOptions({ autoScale: true });
    }
  }, []);

  return (
    <div style={{ position: 'relative' }}>
      <div
        ref={chartContainerRef}
        style={{
          width: '100%',
          height: `${height}px`,
          borderRadius: '8px',
          overflow: 'hidden',
        }}
      />
      {/* Chart controls */}
      <div
        style={{
          position: 'absolute',
          top: '8px',
          right: '8px',
          display: 'flex',
          gap: '4px',
          zIndex: 10,
        }}
      >
        <button
          onClick={handleFitContent}
          style={{
            padding: '4px 8px',
            fontSize: '11px',
            background: '#21262d',
            color: '#e6edf3',
            border: '1px solid #30363d',
            borderRadius: '4px',
            cursor: 'pointer',
          }}
          title="Fit all data"
        >
          Fit
        </button>
        <button
          onClick={handleResetZoom}
          style={{
            padding: '4px 8px',
            fontSize: '11px',
            background: '#21262d',
            color: '#e6edf3',
            border: '1px solid #30363d',
            borderRadius: '4px',
            cursor: 'pointer',
          }}
          title="Reset zoom"
        >
          Reset
        </button>
      </div>
    </div>
  );
}
