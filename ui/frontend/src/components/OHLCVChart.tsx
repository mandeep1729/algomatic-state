import { useEffect, useRef, useCallback } from 'react';
import {
  createChart,
  IChartApi,
  ISeriesApi,
  CandlestickData,
  HistogramData,
  LineData,
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

interface FeatureData {
  timestamps: string[];
  features: Record<string, number[]>;
  feature_names: string[];
}

interface StateInfo {
  state_id: number;
  label: string;
  short_label: string;
  color: string;
  description: string;
}

interface RegimeData {
  timestamps: string[];
  state_ids: number[];
  state_info: Record<string, StateInfo>;
}

interface OHLCVChartProps {
  data: OHLCVData | null;
  featureData?: FeatureData | null;
  regimeData?: RegimeData | null;
  selectedFeatures?: string[];
  showVolume?: boolean;
  showStates?: boolean;
  height?: number;
  onRangeChange?: (start: number, end: number) => void;
}

// Feature overlay colors - cycle through these
const OVERLAY_COLORS = [
  '#58a6ff', '#3fb950', '#f85149', '#d29922', '#a371f7',
  '#db6d28', '#ff7b72', '#7ee787', '#79c0ff', '#cea5fb',
];

// Convert ISO timestamp to Unix timestamp (seconds)
const toUnixTime = (isoString: string): Time => {
  return Math.floor(new Date(isoString).getTime() / 1000) as Time;
};

// Check if feature should use price scale (overlays on price chart)
const isPriceScaleFeature = (featureKey: string): boolean => {
  const priceFeatures = [
    'sma_20', 'sma_50', 'sma_200', 'ema_20', 'ema_50', 'ema_200',
    'bb_upper', 'bb_middle', 'bb_lower', 'vwap', 'vwap_60',
    'psar', 'ichi_tenkan', 'ichi_kijun', 'ichi_senkou_a', 'ichi_senkou_b',
    'pivot_pp', 'pivot_r1', 'pivot_r2', 'pivot_s1', 'pivot_s2',
  ];
  return priceFeatures.includes(featureKey);
};

export function OHLCVChart({
  data,
  featureData,
  regimeData,
  selectedFeatures = [],
  showVolume = true,
  showStates = true,
  height = 500,
  onRangeChange,
}: OHLCVChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candlestickSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<'Histogram'> | null>(null);
  const stateSeriesRef = useRef<ISeriesApi<'Histogram'> | null>(null);
  const featureSeriesRef = useRef<Map<string, ISeriesApi<'Line'>>>(new Map());

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
        top: 0.8,
        bottom: 0.08,
      },
    });

    // Add state series as histogram at very bottom
    const stateSeries = chart.addHistogramSeries({
      priceFormat: {
        type: 'volume',
      },
      priceScaleId: 'states',
    });

    // Configure state scale (below volume)
    chart.priceScale('states').applyOptions({
      scaleMargins: {
        top: 0.95,
        bottom: 0,
      },
    });

    chartRef.current = chart;
    candlestickSeriesRef.current = candlestickSeries;
    volumeSeriesRef.current = volumeSeries;
    stateSeriesRef.current = stateSeries;

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
      stateSeriesRef.current = null;
      featureSeriesRef.current.clear();
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

  // Update feature overlays
  useEffect(() => {
    if (!chartRef.current || !featureData) return;

    const chart = chartRef.current;
    const currentSeries = featureSeriesRef.current;

    // Remove series that are no longer selected
    for (const [key, series] of currentSeries.entries()) {
      if (!selectedFeatures.includes(key)) {
        chart.removeSeries(series);
        currentSeries.delete(key);
      }
    }

    // Add or update series for selected features
    selectedFeatures.forEach((featureKey, index) => {
      const featureValues = featureData.features[featureKey];
      if (!featureValues) return;

      // Assign unique color per indicator using index
      const color = OVERLAY_COLORS[index % OVERLAY_COLORS.length];

      // Prepare line data, filtering out NaN/null values
      const lineData: LineData[] = [];
      for (let i = 0; i < featureData.timestamps.length; i++) {
        const value = featureValues[i];
        if (value !== null && value !== undefined && !isNaN(value) && isFinite(value)) {
          lineData.push({
            time: toUnixTime(featureData.timestamps[i]),
            value: value,
          });
        }
      }

      if (lineData.length === 0) return;

      // Check if series already exists
      let series = currentSeries.get(featureKey);

      if (!series) {
        // Determine price scale
        const priceScaleId = isPriceScaleFeature(featureKey) ? 'right' : `feature_${featureKey}`;

        // Create new series
        series = chart.addLineSeries({
          color: color,
          lineWidth: 2,
          priceScaleId: priceScaleId,
          lastValueVisible: false,
          priceLineVisible: false,
        });

        // Configure separate scale for non-price features
        if (!isPriceScaleFeature(featureKey)) {
          chart.priceScale(`feature_${featureKey}`).applyOptions({
            scaleMargins: {
              top: 0.7,
              bottom: 0.05,
            },
            visible: false,
          });
        }

        currentSeries.set(featureKey, series);
      }

      series.setData(lineData);
    });
  }, [featureData, selectedFeatures]);

  // Update volume visibility
  useEffect(() => {
    if (volumeSeriesRef.current) {
      volumeSeriesRef.current.applyOptions({
        visible: showVolume,
      });
    }
  }, [showVolume]);

  // Update state histogram data
  useEffect(() => {
    if (!stateSeriesRef.current || !regimeData) {
      return;
    }

    const stateData: HistogramData[] = regimeData.timestamps.map((ts, i) => {
      const stateId = regimeData.state_ids[i];
      const stateInfo = regimeData.state_info[String(stateId)];
      return {
        time: toUnixTime(ts),
        value: 1, // Constant height for state bars
        color: stateInfo?.color || '#6b7280',
      };
    });

    stateSeriesRef.current.setData(stateData);
  }, [regimeData]);

  // Update state visibility
  useEffect(() => {
    if (stateSeriesRef.current) {
      stateSeriesRef.current.applyOptions({
        visible: showStates && regimeData !== null,
      });
    }
  }, [showStates, regimeData]);

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
      {/* Feature legend */}
      {selectedFeatures.length > 0 && (
        <div
          style={{
            position: 'absolute',
            top: '8px',
            left: '8px',
            display: 'flex',
            flexWrap: 'wrap',
            gap: '4px',
            zIndex: 10,
            maxWidth: '60%',
          }}
        >
          {selectedFeatures.map((feature, index) => {
            const color = OVERLAY_COLORS[index % OVERLAY_COLORS.length];
            return (
              <span
                key={feature}
                style={{
                  padding: '2px 6px',
                  fontSize: '10px',
                  background: 'rgba(0,0,0,0.7)',
                  color: color,
                  borderRadius: '3px',
                  border: `1px solid ${color}`,
                }}
              >
                {feature}
              </span>
            );
          })}
        </div>
      )}
      {/* State legend */}
      {showStates && regimeData && (
        <div
          style={{
            position: 'absolute',
            bottom: '8px',
            left: '8px',
            display: 'flex',
            flexWrap: 'wrap',
            gap: '4px',
            zIndex: 10,
            maxWidth: '80%',
          }}
        >
          {Object.entries(regimeData.state_info)
            .filter(([key]) => key !== '-1') // Hide unknown state from legend
            .sort(([a], [b]) => Number(a) - Number(b))
            .map(([stateId, info]) => (
              <span
                key={stateId}
                style={{
                  padding: '2px 6px',
                  fontSize: '9px',
                  background: 'rgba(0,0,0,0.8)',
                  color: info.color,
                  borderRadius: '3px',
                  border: `1px solid ${info.color}`,
                }}
                title={info.description}
              >
                {info.short_label}
              </span>
            ))}
        </div>
      )}
    </div>
  );
}
