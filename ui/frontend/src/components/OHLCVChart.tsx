import { useEffect, useRef, useCallback, useState, useMemo } from 'react';
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

const MAX_CHART_POINTS = 7200;
const MIN_CHART_POINTS = 100;

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

  // Timeline range slider state
  const totalPoints = data?.timestamps.length ?? 0;
  const needsSlider = totalPoints > MAX_CHART_POINTS;
  const [sliderStart, setSliderStart] = useState(0);
  const [sliderEnd, setSliderEnd] = useState(Math.min(totalPoints, MAX_CHART_POINTS));

  // Range slider refs for drag handling
  const rangeTrackRef = useRef<HTMLDivElement>(null);
  const dragTypeRef = useRef<'left' | 'right' | 'middle' | null>(null);
  const dragStartXRef = useRef(0);
  const dragStartValuesRef = useRef({ start: 0, end: 0 });

  // Reset slider when data changes
  useEffect(() => {
    setSliderStart(0);
    setSliderEnd(Math.min(totalPoints, MAX_CHART_POINTS));
  }, [data, totalPoints]);

  // Clamp window size to MAX_CHART_POINTS
  const clampedEnd = Math.min(sliderEnd, totalPoints);
  const windowSize = clampedEnd - sliderStart;

  // Compute windowed data subset
  const windowedData = useMemo(() => {
    if (!data) return null;
    if (!needsSlider) return data;
    const start = sliderStart;
    const end = clampedEnd;
    return {
      timestamps: data.timestamps.slice(start, end),
      open: data.open.slice(start, end),
      high: data.high.slice(start, end),
      low: data.low.slice(start, end),
      close: data.close.slice(start, end),
      volume: data.volume.slice(start, end),
    };
  }, [data, needsSlider, sliderStart, clampedEnd]);

  // Compute windowed feature data
  const windowedFeatureData = useMemo(() => {
    if (!featureData || !data) return featureData;
    if (!needsSlider) return featureData;
    const startTime = data.timestamps[sliderStart];
    const endTime = data.timestamps[clampedEnd - 1];
    const startIdx = featureData.timestamps.findIndex((ts) => ts >= startTime);
    const endIdx = featureData.timestamps.findIndex((ts) => ts > endTime);
    const actualEnd = endIdx === -1 ? featureData.timestamps.length : endIdx;
    const actualStart = startIdx === -1 ? 0 : startIdx;
    const windowedFeatures: Record<string, number[]> = {};
    for (const [key, values] of Object.entries(featureData.features)) {
      windowedFeatures[key] = values.slice(actualStart, actualEnd);
    }
    return {
      timestamps: featureData.timestamps.slice(actualStart, actualEnd),
      features: windowedFeatures,
      feature_names: featureData.feature_names,
    };
  }, [featureData, data, needsSlider, sliderStart, clampedEnd]);

  // Compute windowed regime data
  const windowedRegimeData = useMemo(() => {
    if (!regimeData || !data) return regimeData;
    if (!needsSlider) return regimeData;
    const startTime = data.timestamps[sliderStart];
    const endTime = data.timestamps[clampedEnd - 1];
    const startIdx = regimeData.timestamps.findIndex((ts) => ts >= startTime);
    const endIdx = regimeData.timestamps.findIndex((ts) => ts > endTime);
    const actualEnd = endIdx === -1 ? regimeData.timestamps.length : endIdx;
    const actualStart = startIdx === -1 ? 0 : startIdx;
    return {
      timestamps: regimeData.timestamps.slice(actualStart, actualEnd),
      state_ids: regimeData.state_ids.slice(actualStart, actualEnd),
      state_info: regimeData.state_info,
    };
  }, [regimeData, data, needsSlider, sliderStart, clampedEnd]);

  // Drag event handlers for the range slider
  const handleDragStart = useCallback((type: 'left' | 'right' | 'middle', clientX: number) => {
    dragTypeRef.current = type;
    dragStartXRef.current = clientX;
    dragStartValuesRef.current = { start: sliderStart, end: clampedEnd };
  }, [sliderStart, clampedEnd]);

  const handleDragMove = useCallback((clientX: number) => {
    if (!dragTypeRef.current || !rangeTrackRef.current) return;
    const rect = rangeTrackRef.current.getBoundingClientRect();
    const pixelDelta = clientX - dragStartXRef.current;
    const indexDelta = Math.round((pixelDelta / rect.width) * totalPoints);
    const { start: origStart, end: origEnd } = dragStartValuesRef.current;

    if (dragTypeRef.current === 'left') {
      const newStart = Math.max(0, Math.min(origStart + indexDelta, origEnd - MIN_CHART_POINTS));
      const newWindowSize = origEnd - newStart;
      if (newWindowSize <= MAX_CHART_POINTS) {
        setSliderStart(newStart);
      }
    } else if (dragTypeRef.current === 'right') {
      const newEnd = Math.min(totalPoints, Math.max(origEnd + indexDelta, origStart + MIN_CHART_POINTS));
      const newWindowSize = newEnd - origStart;
      if (newWindowSize <= MAX_CHART_POINTS) {
        setSliderEnd(newEnd);
      }
    } else if (dragTypeRef.current === 'middle') {
      const span = origEnd - origStart;
      let newStart = origStart + indexDelta;
      let newEnd = origEnd + indexDelta;
      if (newStart < 0) {
        newStart = 0;
        newEnd = span;
      }
      if (newEnd > totalPoints) {
        newEnd = totalPoints;
        newStart = totalPoints - span;
      }
      setSliderStart(newStart);
      setSliderEnd(newEnd);
    }
  }, [totalPoints]);

  const handleDragEnd = useCallback(() => {
    dragTypeRef.current = null;
  }, []);

  // Mouse event handlers
  useEffect(() => {
    const onMouseMove = (e: MouseEvent) => handleDragMove(e.clientX);
    const onMouseUp = () => handleDragEnd();
    const onTouchMove = (e: TouchEvent) => {
      if (e.touches.length === 1) handleDragMove(e.touches[0].clientX);
    };
    const onTouchEnd = () => handleDragEnd();

    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
    window.addEventListener('touchmove', onTouchMove);
    window.addEventListener('touchend', onTouchEnd);
    return () => {
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
      window.removeEventListener('touchmove', onTouchMove);
      window.removeEventListener('touchend', onTouchEnd);
    };
  }, [handleDragMove, handleDragEnd]);

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
          const day = date.getUTCDate();
          const hours = date.getUTCHours().toString().padStart(2, '0');
          const minutes = date.getUTCMinutes().toString().padStart(2, '0');
          const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
          if (tickMarkType <= 2) {
            return `${months[date.getUTCMonth()]} ${day}`;
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
    if (!windowedData || !candlestickSeriesRef.current || !volumeSeriesRef.current) {
      return;
    }

    // Prepare candlestick data
    const candlestickData: CandlestickData[] = windowedData.timestamps.map((ts, i) => ({
      time: toUnixTime(ts),
      open: windowedData.open[i],
      high: windowedData.high[i],
      low: windowedData.low[i],
      close: windowedData.close[i],
    }));

    // Prepare volume data with colors based on candle direction
    const volumeData: HistogramData[] = windowedData.timestamps.map((ts, i) => {
      const isUp = i === 0 || windowedData.close[i] >= windowedData.open[i];
      return {
        time: toUnixTime(ts),
        value: windowedData.volume[i],
        color: isUp ? 'rgba(63, 185, 80, 0.5)' : 'rgba(248, 81, 73, 0.5)',
      };
    });

    candlestickSeriesRef.current.setData(candlestickData);
    volumeSeriesRef.current.setData(volumeData);

    // Fit content to show all data
    if (chartRef.current) {
      chartRef.current.timeScale().fitContent();
    }
  }, [windowedData]);

  // Update feature overlays
  useEffect(() => {
    if (!chartRef.current || !windowedFeatureData) return;

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
      const featureValues = windowedFeatureData.features[featureKey];
      if (!featureValues) return;

      // Assign unique color per indicator using index
      const color = OVERLAY_COLORS[index % OVERLAY_COLORS.length];

      // Prepare line data, filtering out NaN/null values
      const lineData: LineData[] = [];
      for (let i = 0; i < windowedFeatureData.timestamps.length; i++) {
        const value = featureValues[i];
        if (value !== null && value !== undefined && !isNaN(value) && isFinite(value)) {
          lineData.push({
            time: toUnixTime(windowedFeatureData.timestamps[i]),
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
  }, [windowedFeatureData, selectedFeatures]);

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
    if (!stateSeriesRef.current || !windowedRegimeData) {
      return;
    }

    const stateData: HistogramData[] = windowedRegimeData.timestamps.map((ts, i) => {
      const stateId = windowedRegimeData.state_ids[i];
      const stateInfo = windowedRegimeData.state_info[String(stateId)];
      return {
        time: toUnixTime(ts),
        value: 1, // Constant height for state bars
        color: stateInfo?.color || '#6b7280',
      };
    });

    stateSeriesRef.current.setData(stateData);
  }, [windowedRegimeData]);

  // Update state visibility
  useEffect(() => {
    if (stateSeriesRef.current) {
      stateSeriesRef.current.applyOptions({
        visible: showStates && windowedRegimeData !== null,
      });
    }
  }, [showStates, windowedRegimeData]);

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

  // Format slider label showing the visible date range
  const sliderLabel = useMemo(() => {
    if (!windowedData || windowedData.timestamps.length === 0) return '';
    const startDate = new Date(windowedData.timestamps[0]);
    const endDate = new Date(windowedData.timestamps[windowedData.timestamps.length - 1]);
    const fmt = (d: Date) => {
      const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
      const hrs = d.getUTCHours().toString().padStart(2, '0');
      const mins = d.getUTCMinutes().toString().padStart(2, '0');
      return `${months[d.getUTCMonth()]} ${d.getUTCDate()} ${hrs}:${mins}`;
    };
    return `${fmt(startDate)} - ${fmt(endDate)}`;
  }, [windowedData]);

  return (
    <div style={{ position: 'relative' }}>
      <div
        ref={chartContainerRef}
        style={{
          width: '100%',
          height: `${height}px`,
          borderRadius: needsSlider ? '8px 8px 0 0' : '8px',
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
      {/* Dual-handle range slider for timeline navigation */}
      {needsSlider && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '8px 12px',
            background: '#0d1117',
            borderTop: '1px solid #21262d',
            borderRadius: '0 0 8px 8px',
          }}
        >
          <span
            style={{
              fontSize: '10px',
              color: '#8b949e',
              whiteSpace: 'nowrap',
              minWidth: '32px',
            }}
          >
            {sliderStart + 1}
          </span>
          {/* Range slider track */}
          <div
            ref={rangeTrackRef}
            style={{
              flex: 1,
              position: 'relative',
              height: '20px',
              display: 'flex',
              alignItems: 'center',
              userSelect: 'none',
            }}
          >
            {/* Background track */}
            <div
              style={{
                position: 'absolute',
                left: 0,
                right: 0,
                height: '4px',
                background: '#21262d',
                borderRadius: '2px',
              }}
            />
            {/* Active range fill */}
            <div
              style={{
                position: 'absolute',
                left: `${(sliderStart / totalPoints) * 100}%`,
                width: `${((clampedEnd - sliderStart) / totalPoints) * 100}%`,
                height: '4px',
                background: '#58a6ff',
                borderRadius: '2px',
                cursor: 'grab',
              }}
              onMouseDown={(e) => {
                e.preventDefault();
                handleDragStart('middle', e.clientX);
              }}
              onTouchStart={(e) => {
                if (e.touches.length === 1) {
                  handleDragStart('middle', e.touches[0].clientX);
                }
              }}
            />
            {/* Left handle */}
            <div
              style={{
                position: 'absolute',
                left: `${(sliderStart / totalPoints) * 100}%`,
                width: '12px',
                height: '16px',
                background: '#58a6ff',
                borderRadius: '3px',
                transform: 'translateX(-6px)',
                cursor: 'ew-resize',
                zIndex: 2,
                border: '1px solid #79c0ff',
              }}
              onMouseDown={(e) => {
                e.preventDefault();
                e.stopPropagation();
                handleDragStart('left', e.clientX);
              }}
              onTouchStart={(e) => {
                e.stopPropagation();
                if (e.touches.length === 1) {
                  handleDragStart('left', e.touches[0].clientX);
                }
              }}
            />
            {/* Right handle */}
            <div
              style={{
                position: 'absolute',
                left: `${(clampedEnd / totalPoints) * 100}%`,
                width: '12px',
                height: '16px',
                background: '#58a6ff',
                borderRadius: '3px',
                transform: 'translateX(-6px)',
                cursor: 'ew-resize',
                zIndex: 2,
                border: '1px solid #79c0ff',
              }}
              onMouseDown={(e) => {
                e.preventDefault();
                e.stopPropagation();
                handleDragStart('right', e.clientX);
              }}
              onTouchStart={(e) => {
                e.stopPropagation();
                if (e.touches.length === 1) {
                  handleDragStart('right', e.touches[0].clientX);
                }
              }}
            />
          </div>
          <span
            style={{
              fontSize: '10px',
              color: '#8b949e',
              whiteSpace: 'nowrap',
              minWidth: '32px',
              textAlign: 'right',
            }}
          >
            {clampedEnd}
          </span>
          <span
            style={{
              fontSize: '10px',
              color: '#58a6ff',
              whiteSpace: 'nowrap',
              marginLeft: '4px',
            }}
          >
            {sliderLabel} ({windowSize.toLocaleString()} pts)
          </span>
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
