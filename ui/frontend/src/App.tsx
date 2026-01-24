import { useState, useEffect, useCallback, useMemo } from 'react';
import Plot from 'react-plotly.js';
import type { Data, Layout, PlotRelayoutEvent } from 'plotly.js';
import {
  fetchTickers,
  fetchTickerSummary,
  fetchOHLCVData,
  fetchFeatures,
  fetchRegimes,
  fetchStatistics,
} from './api';
import type { TickerSummary } from './api';
import type {
  Ticker,
  OHLCVData,
  FeatureData,
  RegimeData,
  Statistics,
  ChartSettings,
  RegimeParams,
} from './types';

// Constants
const MAX_DISPLAY_POINTS = 7200;

// Regime colors
const REGIME_COLORS = [
  'rgba(88, 166, 255, 0.3)',   // Blue
  'rgba(63, 185, 80, 0.3)',    // Green
  'rgba(248, 81, 73, 0.3)',    // Red
  'rgba(210, 153, 34, 0.3)',   // Yellow
  'rgba(163, 113, 247, 0.3)',  // Purple
  'rgba(219, 109, 40, 0.3)',   // Orange
  'rgba(56, 139, 253, 0.3)',   // Light Blue
  'rgba(238, 75, 43, 0.3)',    // Coral
  'rgba(121, 192, 255, 0.3)',  // Sky
  'rgba(163, 190, 140, 0.3)',  // Sage
];

const REGIME_COLORS_SOLID = [
  '#58a6ff', '#3fb950', '#f85149', '#d29922', '#a371f7',
  '#db6d28', '#388bfd', '#ee4b2b', '#79c0ff', '#a3be8c',
];

function App() {
  // Tickers from database
  const [tickers, setTickers] = useState<Ticker[]>([]);
  const [selectedTicker, setSelectedTicker] = useState<string>('');
  const [timeframe, setTimeframe] = useState<string>('1Min');
  const [tickerSummary, setTickerSummary] = useState<TickerSummary | null>(null);

  // Internal date range for API calls (from ticker summary)
  const [startDate, setStartDate] = useState<string>('');
  const [endDate, setEndDate] = useState<string>('');

  // Data
  const [ohlcvData, setOhlcvData] = useState<OHLCVData | null>(null);
  const [featureData, setFeatureData] = useState<FeatureData | null>(null);
  const [regimeData, setRegimeData] = useState<RegimeData | null>(null);
  const [statistics, setStatistics] = useState<Statistics | null>(null);

  // View range for the slider (indices into the data arrays)
  const [viewRange, setViewRange] = useState<[number, number]>([0, MAX_DISPLAY_POINTS]);

  // UI state
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'charts' | 'features' | 'stats'>('charts');

  // Chart settings
  const [chartSettings, setChartSettings] = useState<ChartSettings>({
    showVolume: true,
    showRegimes: true,
    selectedFeatures: [],
  });

  // Regime parameters
  const [regimeParams, setRegimeParams] = useState<RegimeParams>({
    n_clusters: 5,
    window_size: 60,
    n_components: 8,
  });

  // Compute total data points and constrained view range
  const totalPoints = ohlcvData?.timestamps.length || 0;

  // Ensure view range is valid and within limits
  const constrainedViewRange = useMemo((): [number, number] => {
    if (totalPoints === 0) return [0, 0];

    let [start, end] = viewRange;

    // Clamp to valid range
    start = Math.max(0, Math.min(start, totalPoints - 1));
    end = Math.max(start + 1, Math.min(end, totalPoints));

    // Enforce max points limit
    if (end - start > MAX_DISPLAY_POINTS) {
      end = start + MAX_DISPLAY_POINTS;
    }

    return [start, end];
  }, [viewRange, totalPoints]);

  // Slice data based on view range
  const visibleOhlcvData = useMemo((): OHLCVData | null => {
    if (!ohlcvData) return null;
    const [start, end] = constrainedViewRange;
    return {
      timestamps: ohlcvData.timestamps.slice(start, end),
      open: ohlcvData.open.slice(start, end),
      high: ohlcvData.high.slice(start, end),
      low: ohlcvData.low.slice(start, end),
      close: ohlcvData.close.slice(start, end),
      volume: ohlcvData.volume.slice(start, end),
    };
  }, [ohlcvData, constrainedViewRange]);

  const visibleFeatureData = useMemo((): FeatureData | null => {
    if (!featureData) return null;
    const [start, end] = constrainedViewRange;
    const slicedFeatures: Record<string, number[]> = {};
    for (const [key, values] of Object.entries(featureData.features)) {
      slicedFeatures[key] = values.slice(start, end);
    }
    return {
      timestamps: featureData.timestamps.slice(start, end),
      features: slicedFeatures,
      feature_names: featureData.feature_names,
    };
  }, [featureData, constrainedViewRange]);

  const visibleRegimeData = useMemo((): RegimeData | null => {
    if (!regimeData) return null;
    const [start, end] = constrainedViewRange;
    // Regime data may have different length due to windowing, find overlap
    const regimeStart = Math.max(0, start);
    const regimeEnd = Math.min(regimeData.timestamps.length, end);

    if (regimeEnd <= regimeStart) return null;

    return {
      timestamps: regimeData.timestamps.slice(regimeStart, regimeEnd),
      regime_labels: regimeData.regime_labels.slice(regimeStart, regimeEnd),
      regime_info: regimeData.regime_info,
      transition_matrix: regimeData.transition_matrix,
      explained_variance: regimeData.explained_variance,
      n_samples: regimeEnd - regimeStart,
    };
  }, [regimeData, constrainedViewRange]);

  // Load tickers from database on mount
  useEffect(() => {
    fetchTickers()
      .then(setTickers)
      .catch((err) => setError(err.message));
  }, []);

  // Fetch ticker summary and populate dates when ticker or timeframe changes
  useEffect(() => {
    if (!selectedTicker) {
      setTickerSummary(null);
      setStartDate('');
      setEndDate('');
      return;
    }

    fetchTickerSummary(selectedTicker)
      .then((summary) => {
        setTickerSummary(summary);

        // Get date range for the selected timeframe
        const tfData = summary.timeframes[timeframe];
        if (tfData && tfData.earliest && tfData.latest) {
          setStartDate(tfData.earliest.split('T')[0]);
          setEndDate(tfData.latest.split('T')[0]);
        } else {
          setStartDate('');
          setEndDate('');
        }
      })
      .catch((err) => {
        console.error('Failed to fetch ticker summary:', err);
        setTickerSummary(null);
      });
  }, [selectedTicker, timeframe]);

  // Reset view range when new data is loaded
  useEffect(() => {
    if (ohlcvData) {
      const endIdx = Math.min(ohlcvData.timestamps.length, MAX_DISPLAY_POINTS);
      setViewRange([0, endIdx]);
    }
  }, [ohlcvData]);

  // Load data when ticker is selected
  const loadData = useCallback(async () => {
    if (!selectedTicker) return;

    setLoading(true);
    setError(null);

    try {
      const start = startDate || undefined;
      const end = endDate || undefined;

      // Load OHLCV data from database (auto-fetches from Alpaca if missing)
      const ohlcv = await fetchOHLCVData(
        selectedTicker,
        timeframe,
        start,
        end
      );
      setOhlcvData(ohlcv);

      // Load features
      const features = await fetchFeatures(
        selectedTicker,
        timeframe,
        start,
        end
      );
      setFeatureData(features);

      // Load regimes
      const regimes = await fetchRegimes(
        selectedTicker,
        timeframe,
        start,
        end,
        regimeParams.n_clusters,
        regimeParams.window_size,
        regimeParams.n_components
      );
      setRegimeData(regimes);

      // Load statistics
      const stats = await fetchStatistics(
        selectedTicker,
        timeframe,
        start,
        end
      );
      setStatistics(stats);
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to load data';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  }, [selectedTicker, timeframe, startDate, endDate, regimeParams]);

  // Handle chart selection/zoom
  const handleChartRelayout = useCallback((event: PlotRelayoutEvent) => {
    if (!ohlcvData) return;

    // Check if this is a range selection
    if (event['xaxis.range[0]'] && event['xaxis.range[1]']) {
      const startTime = new Date(event['xaxis.range[0]'] as string).getTime();
      const endTime = new Date(event['xaxis.range[1]'] as string).getTime();

      // Find indices that correspond to the selected time range
      let newStart = 0;
      let newEnd = ohlcvData.timestamps.length;

      for (let i = 0; i < ohlcvData.timestamps.length; i++) {
        const ts = new Date(ohlcvData.timestamps[i]).getTime();
        if (ts >= startTime && newStart === 0) {
          newStart = i;
        }
        if (ts <= endTime) {
          newEnd = i + 1;
        }
      }

      // Enforce max points limit
      if (newEnd - newStart > MAX_DISPLAY_POINTS) {
        newEnd = newStart + MAX_DISPLAY_POINTS;
      }

      setViewRange([newStart, newEnd]);
    }

    // Handle autorange/reset
    if (event['xaxis.autorange']) {
      const endIdx = Math.min(ohlcvData.timestamps.length, MAX_DISPLAY_POINTS);
      setViewRange([0, endIdx]);
    }
  }, [ohlcvData]);

  // Handle range slider change
  const handleRangeChange = (newStart: number, newEnd: number) => {
    // Enforce max points
    if (newEnd - newStart > MAX_DISPLAY_POINTS) {
      // Adjust end to respect max points from start
      newEnd = newStart + MAX_DISPLAY_POINTS;
    }
    setViewRange([newStart, newEnd]);
  };

  // Create candlestick chart data
  const createCandlestickChart = (): { data: Data[]; layout: Partial<Layout> } => {
    if (!visibleOhlcvData) {
      return { data: [], layout: {} };
    }

    const traces: Data[] = [];

    // Candlestick trace
    traces.push({
      type: 'candlestick',
      x: visibleOhlcvData.timestamps,
      open: visibleOhlcvData.open,
      high: visibleOhlcvData.high,
      low: visibleOhlcvData.low,
      close: visibleOhlcvData.close,
      name: 'Price',
      increasing: { line: { color: '#3fb950' } },
      decreasing: { line: { color: '#f85149' } },
    });

    // Add regime backgrounds if enabled
    if (chartSettings.showRegimes && visibleRegimeData && visibleRegimeData.timestamps.length > 0) {
      const shapes: Partial<Plotly.Shape>[] = [];
      let currentRegime = visibleRegimeData.regime_labels[0];
      let startIdx = 0;

      for (let i = 1; i <= visibleRegimeData.regime_labels.length; i++) {
        if (i === visibleRegimeData.regime_labels.length || visibleRegimeData.regime_labels[i] !== currentRegime) {
          shapes.push({
            type: 'rect',
            xref: 'x',
            yref: 'paper',
            x0: visibleRegimeData.timestamps[startIdx],
            x1: visibleRegimeData.timestamps[Math.min(i, visibleRegimeData.regime_labels.length - 1)],
            y0: 0,
            y1: 1,
            fillcolor: REGIME_COLORS[currentRegime % REGIME_COLORS.length],
            line: { width: 0 },
            layer: 'below',
          });

          if (i < visibleRegimeData.regime_labels.length) {
            currentRegime = visibleRegimeData.regime_labels[i];
            startIdx = i;
          }
        }
      }

      return {
        data: traces,
        layout: {
          title: { text: 'Price Chart with Regime States' },
          xaxis: {
            title: { text: 'Time' },
            rangeslider: { visible: false },
            type: 'date',
          },
          yaxis: { title: { text: 'Price' } },
          shapes,
          paper_bgcolor: '#161b22',
          plot_bgcolor: '#0d1117',
          font: { color: '#e6edf3' },
          showlegend: true,
          legend: { x: 0, y: 1.1, orientation: 'h' },
          dragmode: 'select',
        },
      };
    }

    return {
      data: traces,
      layout: {
        title: { text: 'Price Chart' },
        xaxis: {
          title: { text: 'Time' },
          rangeslider: { visible: false },
          type: 'date',
        },
        yaxis: { title: { text: 'Price' } },
        paper_bgcolor: '#161b22',
        plot_bgcolor: '#0d1117',
        font: { color: '#e6edf3' },
        dragmode: 'select',
      },
    };
  };

  // Create volume chart
  const createVolumeChart = (): { data: Data[]; layout: Partial<Layout> } => {
    if (!visibleOhlcvData) {
      return { data: [], layout: {} };
    }

    const colors = visibleOhlcvData.close.map((close, i) =>
      i === 0 || close >= visibleOhlcvData.open[i] ? '#3fb950' : '#f85149'
    );

    return {
      data: [
        {
          type: 'bar',
          x: visibleOhlcvData.timestamps,
          y: visibleOhlcvData.volume,
          marker: { color: colors },
          name: 'Volume',
        },
      ],
      layout: {
        title: { text: 'Volume' },
        xaxis: { title: { text: 'Time' }, type: 'date' },
        yaxis: { title: { text: 'Volume' } },
        paper_bgcolor: '#161b22',
        plot_bgcolor: '#0d1117',
        font: { color: '#e6edf3' },
        height: 200,
      },
    };
  };

  // Create regime distribution chart
  const createRegimeDistribution = (): { data: Data[]; layout: Partial<Layout> } => {
    if (!visibleRegimeData) {
      return { data: [], layout: {} };
    }

    const labels = visibleRegimeData.regime_info.map((r) => `Regime ${r.label}`);
    const values = visibleRegimeData.regime_info.map((r) => r.size);
    const colors = visibleRegimeData.regime_info.map((r) => REGIME_COLORS_SOLID[r.label % REGIME_COLORS_SOLID.length]);

    return {
      data: [
        {
          type: 'pie',
          labels,
          values,
          marker: { colors },
          hole: 0.4,
          textinfo: 'label+percent',
          textfont: { color: '#e6edf3' },
        },
      ],
      layout: {
        title: { text: 'Regime Distribution' },
        paper_bgcolor: '#161b22',
        plot_bgcolor: '#0d1117',
        font: { color: '#e6edf3' },
        height: 300,
        showlegend: false,
      },
    };
  };

  // Create regime performance chart
  const createRegimePerformance = (): { data: Data[]; layout: Partial<Layout> } => {
    if (!visibleRegimeData) {
      return { data: [], layout: {} };
    }

    const sortedRegimes = [...visibleRegimeData.regime_info].sort((a, b) => b.sharpe - a.sharpe);

    return {
      data: [
        {
          type: 'bar',
          x: sortedRegimes.map((r) => `Regime ${r.label}`),
          y: sortedRegimes.map((r) => r.sharpe),
          marker: {
            color: sortedRegimes.map((r) =>
              r.sharpe > 0 ? '#3fb950' : '#f85149'
            ),
          },
          name: 'Sharpe Ratio',
        },
      ],
      layout: {
        title: { text: 'Regime Performance (Sharpe Ratio)' },
        xaxis: { title: { text: 'Regime' } },
        yaxis: { title: { text: 'Sharpe Ratio' } },
        paper_bgcolor: '#161b22',
        plot_bgcolor: '#0d1117',
        font: { color: '#e6edf3' },
        height: 300,
      },
    };
  };

  // Create feature chart
  const createFeatureChart = (featureName: string): { data: Data[]; layout: Partial<Layout> } => {
    if (!visibleFeatureData || !visibleFeatureData.features[featureName]) {
      return { data: [], layout: {} };
    }

    return {
      data: [
        {
          type: 'scatter',
          mode: 'lines',
          x: visibleFeatureData.timestamps,
          y: visibleFeatureData.features[featureName],
          name: featureName,
          line: { color: '#58a6ff' },
        },
      ],
      layout: {
        title: { text: featureName },
        xaxis: { title: { text: 'Time' }, type: 'date' },
        yaxis: { title: { text: 'Value' } },
        paper_bgcolor: '#161b22',
        plot_bgcolor: '#0d1117',
        font: { color: '#e6edf3' },
        height: 200,
      },
    };
  };

  // Create transition matrix heatmap
  const createTransitionMatrix = (): { data: Data[]; layout: Partial<Layout> } => {
    if (!visibleRegimeData || !visibleRegimeData.transition_matrix.length) {
      return { data: [], layout: {} };
    }

    const labels = visibleRegimeData.regime_info.map((r) => `R${r.label}`);

    return {
      data: [
        {
          type: 'heatmap',
          z: visibleRegimeData.transition_matrix,
          x: labels,
          y: labels,
          colorscale: 'Blues',
          showscale: true,
          hovertemplate: 'From %{y} to %{x}: %{z:.2%}<extra></extra>',
        },
      ],
      layout: {
        title: { text: 'Regime Transition Probabilities' },
        xaxis: { title: { text: 'To Regime' } },
        yaxis: { title: { text: 'From Regime' }, autorange: 'reversed' },
        paper_bgcolor: '#161b22',
        plot_bgcolor: '#0d1117',
        font: { color: '#e6edf3' },
        height: 350,
      },
    };
  };

  const toggleFeature = (feature: string) => {
    setChartSettings((prev) => ({
      ...prev,
      selectedFeatures: prev.selectedFeatures.includes(feature)
        ? prev.selectedFeatures.filter((f) => f !== feature)
        : [...prev.selectedFeatures, feature],
    }));
  };

  // Format timestamp for display
  const formatTimestamp = (ts: string) => {
    const date = new Date(ts);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  return (
    <div className="app">
      <header className="header">
        <h1>Regime State Visualization</h1>
        <div>
          {loading && <span style={{ color: '#58a6ff' }}>Loading...</span>}
        </div>
      </header>

      <div className="main-content">
        {/* Sidebar */}
        <aside className="sidebar">
          {/* Ticker Selection */}
          <div className="section">
            <h3 className="section-title">Ticker</h3>
            <div className="form-group">
              <label>Symbol</label>
              <select
                value={selectedTicker}
                onChange={(e) => setSelectedTicker(e.target.value)}
              >
                <option value="">Select ticker...</option>
                {tickers.map((t) => (
                  <option key={t.symbol} value={t.symbol}>
                    {t.symbol} {t.timeframes.length > 0 ? `(${t.timeframes.join(', ')})` : ''}
                  </option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label>Timeframe</label>
              <select
                value={timeframe}
                onChange={(e) => setTimeframe(e.target.value)}
              >
                <option value="1Min">1 Minute</option>
                <option value="5Min">5 Minutes</option>
                <option value="15Min">15 Minutes</option>
                <option value="1Hour">1 Hour</option>
                <option value="1Day">1 Day</option>
              </select>
            </div>

            {tickerSummary && tickerSummary.timeframes[timeframe] && (
              <div style={{ fontSize: '0.75rem', color: '#8b949e', marginTop: '0.5rem' }}>
                Available: {tickerSummary.timeframes[timeframe].bar_count.toLocaleString()} bars
              </div>
            )}
            {selectedTicker && (!tickerSummary?.timeframes[timeframe]?.bar_count) && (
              <div style={{ fontSize: '0.75rem', color: '#d29922', marginTop: '0.5rem' }}>
                No data in DB. Will fetch from Alpaca on load.
              </div>
            )}
          </div>

          {/* Regime Parameters */}
          <div className="section">
            <h3 className="section-title">Regime Parameters</h3>
            <div className="form-group">
              <label>Number of Clusters</label>
              <div className="slider-container">
                <input
                  type="range"
                  min="2"
                  max="10"
                  value={regimeParams.n_clusters}
                  onChange={(e) =>
                    setRegimeParams((p) => ({
                      ...p,
                      n_clusters: parseInt(e.target.value),
                    }))
                  }
                />
                <div className="slider-value">{regimeParams.n_clusters}</div>
              </div>
            </div>
            <div className="form-group">
              <label>Window Size</label>
              <div className="slider-container">
                <input
                  type="range"
                  min="20"
                  max="120"
                  step="10"
                  value={regimeParams.window_size}
                  onChange={(e) =>
                    setRegimeParams((p) => ({
                      ...p,
                      window_size: parseInt(e.target.value),
                    }))
                  }
                />
                <div className="slider-value">{regimeParams.window_size}</div>
              </div>
            </div>
            <div className="form-group">
              <label>PCA Components</label>
              <div className="slider-container">
                <input
                  type="range"
                  min="2"
                  max="16"
                  value={regimeParams.n_components}
                  onChange={(e) =>
                    setRegimeParams((p) => ({
                      ...p,
                      n_components: parseInt(e.target.value),
                    }))
                  }
                />
                <div className="slider-value">{regimeParams.n_components}</div>
              </div>
            </div>
          </div>

          {/* Load Button */}
          <button
            className="btn btn-primary"
            style={{ width: '100%', marginBottom: '1rem' }}
            onClick={loadData}
            disabled={!selectedTicker || loading}
          >
            {loading ? 'Loading...' : 'Load Data'}
          </button>

          {/* Chart Settings */}
          <div className="section">
            <h3 className="section-title">Display Options</h3>
            <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.875rem' }}>
              <input
                type="checkbox"
                checked={chartSettings.showVolume}
                onChange={(e) =>
                  setChartSettings((s) => ({ ...s, showVolume: e.target.checked }))
                }
              />
              Show Volume
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.875rem', marginTop: '0.5rem' }}>
              <input
                type="checkbox"
                checked={chartSettings.showRegimes}
                onChange={(e) =>
                  setChartSettings((s) => ({ ...s, showRegimes: e.target.checked }))
                }
              />
              Show Regime Backgrounds
            </label>
          </div>

          {/* Regime Legend */}
          {regimeData && (
            <div className="section">
              <h3 className="section-title">Regime Legend</h3>
              <div className="regime-legend">
                {regimeData.regime_info.map((r) => (
                  <div key={r.label} className="regime-item">
                    <div
                      className="regime-color"
                      style={{
                        backgroundColor: REGIME_COLORS_SOLID[r.label % REGIME_COLORS_SOLID.length],
                      }}
                    />
                    <span>R{r.label}: {r.sharpe.toFixed(2)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </aside>

        {/* Main Chart Area */}
        <main className="chart-area">
          {error && <div className="error">{error}</div>}

          {/* Tabs */}
          <div className="tabs">
            <button
              className={`tab ${activeTab === 'charts' ? 'active' : ''}`}
              onClick={() => setActiveTab('charts')}
            >
              Charts
            </button>
            <button
              className={`tab ${activeTab === 'features' ? 'active' : ''}`}
              onClick={() => setActiveTab('features')}
            >
              Features
            </button>
            <button
              className={`tab ${activeTab === 'stats' ? 'active' : ''}`}
              onClick={() => setActiveTab('stats')}
            >
              Statistics
            </button>
          </div>

          {/* Range Slider - shown when data is loaded */}
          {ohlcvData && ohlcvData.timestamps.length > 0 && (
            <div className="range-slider-container" style={{
              background: '#161b22',
              padding: '1rem',
              borderRadius: '8px',
              marginBottom: '1rem',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                <span style={{ fontSize: '0.875rem', color: '#8b949e' }}>
                  Time Range Selection
                </span>
                <span style={{ fontSize: '0.75rem', color: '#58a6ff' }}>
                  Showing {constrainedViewRange[1] - constrainedViewRange[0]} of {totalPoints.toLocaleString()} points (max {MAX_DISPLAY_POINTS.toLocaleString()})
                </span>
              </div>

              {/* Current range display */}
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.75rem', fontSize: '0.8rem', color: '#e6edf3' }}>
                <span>{ohlcvData.timestamps[constrainedViewRange[0]] ? formatTimestamp(ohlcvData.timestamps[constrainedViewRange[0]]) : '-'}</span>
                <span>{ohlcvData.timestamps[constrainedViewRange[1] - 1] ? formatTimestamp(ohlcvData.timestamps[constrainedViewRange[1] - 1]) : '-'}</span>
              </div>

              {/* Dual-thumb range slider */}
              <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
                <input
                  type="range"
                  min={0}
                  max={Math.max(0, totalPoints - 1)}
                  value={constrainedViewRange[0]}
                  onChange={(e) => {
                    const newStart = parseInt(e.target.value);
                    handleRangeChange(newStart, Math.max(newStart + 1, constrainedViewRange[1]));
                  }}
                  style={{ flex: 1 }}
                />
                <input
                  type="range"
                  min={1}
                  max={totalPoints}
                  value={constrainedViewRange[1]}
                  onChange={(e) => {
                    const newEnd = parseInt(e.target.value);
                    handleRangeChange(Math.min(constrainedViewRange[0], newEnd - 1), newEnd);
                  }}
                  style={{ flex: 1 }}
                />
                <button
                  className="btn"
                  style={{ padding: '0.25rem 0.75rem', fontSize: '0.75rem' }}
                  onClick={() => {
                    const endIdx = Math.min(totalPoints, MAX_DISPLAY_POINTS);
                    setViewRange([0, endIdx]);
                  }}
                >
                  Reset
                </button>
              </div>

              {/* Quick range buttons */}
              <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.75rem', flexWrap: 'wrap' }}>
                {[1000, 2000, 5000, 7200].map((points) => (
                  <button
                    key={points}
                    className="btn"
                    style={{ padding: '0.2rem 0.5rem', fontSize: '0.7rem' }}
                    onClick={() => {
                      const pts = Math.min(points, totalPoints);
                      setViewRange([constrainedViewRange[0], constrainedViewRange[0] + pts]);
                    }}
                    disabled={points > totalPoints}
                  >
                    {points.toLocaleString()} pts
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Charts Tab */}
          {activeTab === 'charts' && (
            <>
              {visibleOhlcvData && (
                <>
                  <div className="chart-container">
                    <Plot
                      data={createCandlestickChart().data}
                      layout={createCandlestickChart().layout}
                      config={{ responsive: true, displayModeBar: true }}
                      style={{ width: '100%', height: '500px' }}
                      onRelayout={handleChartRelayout}
                    />
                  </div>

                  {chartSettings.showVolume && (
                    <div className="chart-container">
                      <Plot
                        data={createVolumeChart().data}
                        layout={createVolumeChart().layout}
                        config={{ responsive: true }}
                        style={{ width: '100%' }}
                      />
                    </div>
                  )}
                </>
              )}

              {visibleRegimeData && (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                  <div className="chart-container">
                    <Plot
                      data={createRegimeDistribution().data}
                      layout={createRegimeDistribution().layout}
                      config={{ responsive: true }}
                      style={{ width: '100%' }}
                    />
                  </div>
                  <div className="chart-container">
                    <Plot
                      data={createRegimePerformance().data}
                      layout={createRegimePerformance().layout}
                      config={{ responsive: true }}
                      style={{ width: '100%' }}
                    />
                  </div>
                  <div className="chart-container" style={{ gridColumn: 'span 2' }}>
                    <Plot
                      data={createTransitionMatrix().data}
                      layout={createTransitionMatrix().layout}
                      config={{ responsive: true }}
                      style={{ width: '100%' }}
                    />
                  </div>
                </div>
              )}

              {!visibleOhlcvData && !loading && (
                <div className="loading">
                  Select a ticker and click "Load Data" to begin
                </div>
              )}
            </>
          )}

          {/* Features Tab */}
          {activeTab === 'features' && (
            <>
              {visibleFeatureData && (
                <>
                  <div className="section">
                    <h3 className="section-title">Select Features to Display</h3>
                    <div className="toggle-group">
                      {visibleFeatureData.feature_names.map((feature) => (
                        <button
                          key={feature}
                          className={`toggle-btn ${
                            chartSettings.selectedFeatures.includes(feature) ? 'active' : ''
                          }`}
                          onClick={() => toggleFeature(feature)}
                        >
                          {feature}
                        </button>
                      ))}
                    </div>
                  </div>

                  {chartSettings.selectedFeatures.map((feature) => (
                    <div key={feature} className="chart-container">
                      <Plot
                        data={createFeatureChart(feature).data}
                        layout={createFeatureChart(feature).layout}
                        config={{ responsive: true }}
                        style={{ width: '100%' }}
                      />
                    </div>
                  ))}

                  {chartSettings.selectedFeatures.length === 0 && (
                    <div className="loading">
                      Select features above to display their charts
                    </div>
                  )}
                </>
              )}

              {!visibleFeatureData && !loading && (
                <div className="loading">Load data to view features</div>
              )}
            </>
          )}

          {/* Statistics Tab */}
          {activeTab === 'stats' && (
            <>
              {statistics && (
                <>
                  {/* OHLCV Stats */}
                  <div className="section">
                    <h3 className="section-title">Price Data Summary</h3>
                    <div className="stats-grid">
                      <div className="stat-item">
                        <div className="stat-label">Total Bars</div>
                        <div className="stat-value">
                          {statistics.ohlcv_stats.total_bars.toLocaleString()}
                        </div>
                      </div>
                      <div className="stat-item">
                        <div className="stat-label">Date Range</div>
                        <div className="stat-value" style={{ fontSize: '0.75rem' }}>
                          {statistics.ohlcv_stats.date_range.start.split(' ')[0]} to{' '}
                          {statistics.ohlcv_stats.date_range.end.split(' ')[0]}
                        </div>
                      </div>
                      <div className="stat-item">
                        <div className="stat-label">Current Price</div>
                        <div className="stat-value">
                          ${statistics.ohlcv_stats.price.current.toFixed(2)}
                        </div>
                      </div>
                      <div className="stat-item">
                        <div className="stat-label">Total Return</div>
                        <div
                          className={`stat-value ${
                            statistics.ohlcv_stats.returns.total_return >= 0
                              ? 'positive'
                              : 'negative'
                          }`}
                        >
                          {statistics.ohlcv_stats.returns.total_return >= 0 ? '+' : ''}
                          {statistics.ohlcv_stats.returns.total_return.toFixed(2)}%
                        </div>
                      </div>
                      <div className="stat-item">
                        <div className="stat-label">Price Range</div>
                        <div className="stat-value">
                          ${statistics.ohlcv_stats.price.min.toFixed(2)} -{' '}
                          ${statistics.ohlcv_stats.price.max.toFixed(2)}
                        </div>
                      </div>
                      <div className="stat-item">
                        <div className="stat-label">Daily Volatility</div>
                        <div className="stat-value">
                          {statistics.ohlcv_stats.returns.daily_volatility.toFixed(3)}%
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Regime Stats */}
                  {statistics.regime_stats.regimes && (
                    <div className="section">
                      <h3 className="section-title">Regime Statistics</h3>
                      <table className="table">
                        <thead>
                          <tr>
                            <th>Regime</th>
                            <th>Samples</th>
                            <th>Mean Return</th>
                            <th>Std Return</th>
                            <th>Sharpe</th>
                          </tr>
                        </thead>
                        <tbody>
                          {statistics.regime_stats.regimes.map((r) => (
                            <tr key={r.label}>
                              <td>
                                <span
                                  style={{
                                    display: 'inline-block',
                                    width: 12,
                                    height: 12,
                                    borderRadius: 2,
                                    backgroundColor:
                                      REGIME_COLORS_SOLID[r.label % REGIME_COLORS_SOLID.length],
                                    marginRight: 8,
                                    verticalAlign: 'middle',
                                  }}
                                />
                                Regime {r.label}
                              </td>
                              <td>{r.size.toLocaleString()}</td>
                              <td
                                className={r.mean_return >= 0 ? 'positive' : 'negative'}
                                style={{ color: r.mean_return >= 0 ? '#3fb950' : '#f85149' }}
                              >
                                {(r.mean_return * 100).toFixed(4)}%
                              </td>
                              <td>{(r.std_return * 100).toFixed(4)}%</td>
                              <td
                                style={{ color: r.sharpe >= 0 ? '#3fb950' : '#f85149' }}
                              >
                                {r.sharpe.toFixed(2)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      {statistics.regime_stats.explained_variance && (
                        <div style={{ marginTop: '0.75rem', fontSize: '0.875rem', color: '#8b949e' }}>
                          PCA Explained Variance:{' '}
                          {(statistics.regime_stats.explained_variance * 100).toFixed(1)}%
                        </div>
                      )}
                    </div>
                  )}

                  {/* Feature Stats */}
                  <div className="section">
                    <h3 className="section-title">Feature Statistics</h3>
                    <div style={{ maxHeight: '400px', overflow: 'auto' }}>
                      <table className="table">
                        <thead>
                          <tr>
                            <th>Feature</th>
                            <th>Min</th>
                            <th>Max</th>
                            <th>Mean</th>
                            <th>Std</th>
                            <th>Median</th>
                          </tr>
                        </thead>
                        <tbody>
                          {Object.entries(statistics.feature_stats).map(([name, stats]) => (
                            <tr key={name}>
                              <td>{name}</td>
                              <td>{stats.min.toFixed(4)}</td>
                              <td>{stats.max.toFixed(4)}</td>
                              <td>{stats.mean.toFixed(4)}</td>
                              <td>{stats.std.toFixed(4)}</td>
                              <td>{stats.median.toFixed(4)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </>
              )}

              {!statistics && !loading && (
                <div className="loading">Load data to view statistics</div>
              )}
            </>
          )}
        </main>
      </div>
    </div>
  );
}

export default App;
