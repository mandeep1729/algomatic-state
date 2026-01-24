import { useState, useEffect, useCallback, useMemo } from 'react';
import Plot from 'react-plotly.js';
import type { Data, Layout } from 'plotly.js';
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
import { OHLCVChart } from './components';

// Constants
const MAX_DISPLAY_POINTS = 7200;

// Regime colors (solid)
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

  // Load data with explicit parameters (avoids stale state issues)
  const loadDataWithParams = useCallback(async (
    ticker: string,
    tf: string,
    start: string,
    end: string
  ) => {
    if (!ticker || !start || !end) return;

    setLoading(true);
    setError(null);

    try {
      // Load OHLCV data from database (auto-fetches from Alpaca if missing)
      const ohlcv = await fetchOHLCVData(ticker, tf, start, end);
      setOhlcvData(ohlcv);

      // Load features
      const features = await fetchFeatures(ticker, tf, start, end);
      setFeatureData(features);

      // Load regimes
      const regimes = await fetchRegimes(
        ticker, tf, start, end,
        regimeParams.n_clusters,
        regimeParams.window_size,
        regimeParams.n_components
      );
      setRegimeData(regimes);

      // Load statistics
      const stats = await fetchStatistics(ticker, tf, start, end);
      setStatistics(stats);

      // Refresh ticker summary to get updated bar counts after fetch
      const updatedSummary = await fetchTickerSummary(ticker);
      setTickerSummary(updatedSummary);
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to load data';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  }, [regimeParams]);

  // Helper to get default date range (last 30 days)
  const getDefaultDateRange = () => {
    const end = new Date();
    const start = new Date();
    start.setDate(start.getDate() - 30);
    return {
      start: start.toISOString().split('T')[0],
      end: end.toISOString().split('T')[0],
    };
  };

  // Fetch ticker summary and auto-load data when ticker changes
  useEffect(() => {
    if (!selectedTicker) {
      setTickerSummary(null);
      setOhlcvData(null);
      setFeatureData(null);
      setRegimeData(null);
      setStatistics(null);
      return;
    }

    // Clear previous data when switching tickers
    setOhlcvData(null);
    setFeatureData(null);
    setRegimeData(null);
    setStatistics(null);

    fetchTickerSummary(selectedTicker)
      .then((summary) => {
        setTickerSummary(summary);

        // Find available timeframes with data
        const availableTimeframes = Object.keys(summary.timeframes).filter(
          tf => summary.timeframes[tf].bar_count > 0
        );

        let selectedTf = timeframe;
        let start: string;
        let end: string;

        if (availableTimeframes.length > 0) {
          // Data exists - use available timeframe and its date range
          if (!availableTimeframes.includes(timeframe)) {
            selectedTf = availableTimeframes[0];
            setTimeframe(selectedTf);
          }
          const tfData = summary.timeframes[selectedTf];
          start = tfData.earliest!.split('T')[0];
          end = tfData.latest!.split('T')[0];
        } else {
          // No data exists - use default dates to trigger Alpaca fetch
          selectedTf = '1Min';
          setTimeframe(selectedTf);
          const defaults = getDefaultDateRange();
          start = defaults.start;
          end = defaults.end;
        }

        // Load data with determined values
        loadDataWithParams(selectedTicker, selectedTf, start, end);
      })
      .catch((err) => {
        console.error('Failed to fetch ticker summary:', err);
        setTickerSummary(null);
        // Still try to load with default dates
        const defaults = getDefaultDateRange();
        loadDataWithParams(selectedTicker, '1Min', defaults.start, defaults.end);
      });
  }, [selectedTicker, loadDataWithParams]);

  // Load data when timeframe changes (only if we have summary data)
  useEffect(() => {
    // Skip if no ticker selected or if this is initial mount
    if (!selectedTicker || !tickerSummary) return;

    // Check if this timeframe has data
    const tfData = tickerSummary.timeframes[timeframe];
    if (tfData && tfData.earliest && tfData.latest) {
      const start = tfData.earliest.split('T')[0];
      const end = tfData.latest.split('T')[0];
      loadDataWithParams(selectedTicker, timeframe, start, end);
    } else {
      // No data for this timeframe - use default dates to trigger fetch
      const defaults = getDefaultDateRange();
      loadDataWithParams(selectedTicker, timeframe, defaults.start, defaults.end);
    }
  }, [timeframe]); // Only depend on timeframe changes, not tickerSummary

  // Reset view range when new data is loaded
  useEffect(() => {
    if (ohlcvData) {
      const endIdx = Math.min(ohlcvData.timestamps.length, MAX_DISPLAY_POINTS);
      setViewRange([0, endIdx]);
    }
  }, [ohlcvData]);

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
            <h3 className="section-title">Data Selection</h3>
            <div className="form-group">
              <label>Ticker</label>
              <select
                value={selectedTicker}
                onChange={(e) => setSelectedTicker(e.target.value)}
              >
                <option value="">Select ticker...</option>
                {tickers.map((t) => (
                  <option key={t.symbol} value={t.symbol}>
                    {t.symbol}
                  </option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label>Timeframe</label>
              <select
                value={timeframe}
                onChange={(e) => setTimeframe(e.target.value)}
                disabled={!selectedTicker || loading || !tickerSummary || Object.keys(tickerSummary.timeframes).length === 0}
              >
                {['1Min', '5Min', '15Min', '1Hour', '1Day'].map((tf) => {
                  const tfData = tickerSummary?.timeframes[tf];
                  const barCount = tfData?.bar_count || 0;
                  return (
                    <option key={tf} value={tf}>
                      {tf}{barCount > 0 ? ` (${barCount.toLocaleString()} bars)` : ''}
                    </option>
                  );
                })}
              </select>
            </div>

            {loading && (
              <div style={{ fontSize: '0.75rem', color: '#58a6ff', marginTop: '0.5rem' }}>
                {tickerSummary && Object.keys(tickerSummary.timeframes).length === 0
                  ? 'Fetching data from Alpaca...'
                  : 'Loading data...'}
              </div>
            )}
            {error && (
              <div style={{ fontSize: '0.75rem', color: '#f85149', marginTop: '0.5rem' }}>
                {error}
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
          {ohlcvData && ohlcvData.timestamps.length > 0 && (() => {
            const windowSize = constrainedViewRange[1] - constrainedViewRange[0];
            const windowWidthPercent = (windowSize / totalPoints) * 100;
            const windowPositionPercent = (constrainedViewRange[0] / totalPoints) * 100;

            return (
              <div className="range-slider-container" style={{
                background: '#161b22',
                padding: '1rem',
                borderRadius: '8px',
                marginBottom: '1rem',
              }}>
                {/* Header with info */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                  <span style={{ fontSize: '0.875rem', color: '#8b949e' }}>
                    Time Range Selection
                  </span>
                  <span style={{ fontSize: '0.75rem', color: '#58a6ff' }}>
                    Showing {windowSize.toLocaleString()} of {totalPoints.toLocaleString()} points
                  </span>
                </div>

                {/* Min/Max date labels */}
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.25rem', fontSize: '0.7rem', color: '#6e7681' }}>
                  <span>{formatTimestamp(ohlcvData.timestamps[0])}</span>
                  <span>{formatTimestamp(ohlcvData.timestamps[totalPoints - 1])}</span>
                </div>

                {/* Window slider track */}
                <div
                  style={{
                    position: 'relative',
                    height: '40px',
                    background: '#21262d',
                    borderRadius: '4px',
                    cursor: 'pointer',
                    border: '1px solid #30363d',
                  }}
                  onClick={(e) => {
                    const rect = e.currentTarget.getBoundingClientRect();
                    const clickPercent = (e.clientX - rect.left) / rect.width;
                    const clickIndex = Math.floor(clickPercent * totalPoints);
                    const halfWindow = Math.floor(windowSize / 2);
                    const newStart = Math.max(0, Math.min(clickIndex - halfWindow, totalPoints - windowSize));
                    setViewRange([newStart, newStart + windowSize]);
                  }}
                >
                  {/* Draggable window */}
                  <div
                    style={{
                      position: 'absolute',
                      left: `${windowPositionPercent}%`,
                      width: `${Math.max(windowWidthPercent, 2)}%`,
                      height: '100%',
                      background: 'linear-gradient(180deg, #388bfd 0%, #1f6feb 100%)',
                      borderRadius: '4px',
                      cursor: 'grab',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      minWidth: '20px',
                    }}
                    draggable={false}
                    onMouseDown={(e) => {
                      e.preventDefault();
                      const startX = e.clientX;
                      const startPosition = constrainedViewRange[0];
                      const track = e.currentTarget.parentElement;
                      if (!track) return;
                      const trackWidth = track.getBoundingClientRect().width;

                      const onMouseMove = (moveEvent: MouseEvent) => {
                        const deltaX = moveEvent.clientX - startX;
                        const deltaIndex = Math.round((deltaX / trackWidth) * totalPoints);
                        const newStart = Math.max(0, Math.min(startPosition + deltaIndex, totalPoints - windowSize));
                        setViewRange([newStart, newStart + windowSize]);
                      };

                      const onMouseUp = () => {
                        document.removeEventListener('mousemove', onMouseMove);
                        document.removeEventListener('mouseup', onMouseUp);
                      };

                      document.addEventListener('mousemove', onMouseMove);
                      document.addEventListener('mouseup', onMouseUp);
                    }}
                  >
                    <span style={{ fontSize: '0.65rem', color: '#fff', fontWeight: 500, pointerEvents: 'none' }}>
                      ⋮⋮
                    </span>
                  </div>
                </div>

                {/* Current view range display */}
                <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '0.5rem', fontSize: '0.8rem', color: '#e6edf3' }}>
                  <span>{formatTimestamp(ohlcvData.timestamps[constrainedViewRange[0]])}</span>
                  <span style={{ color: '#8b949e', fontSize: '0.7rem' }}>
                    {windowSize.toLocaleString()} points
                  </span>
                  <span>{formatTimestamp(ohlcvData.timestamps[constrainedViewRange[1] - 1])}</span>
                </div>

                {/* Window size buttons */}
                <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.75rem', flexWrap: 'wrap', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.75rem', color: '#8b949e' }}>Window:</span>
                  {[1000, 2000, 3600, 7200].map((points) => (
                    <button
                      key={points}
                      className="btn"
                      style={{
                        padding: '0.2rem 0.5rem',
                        fontSize: '0.7rem',
                        background: windowSize === points ? '#388bfd' : undefined,
                      }}
                      onClick={() => {
                        const pts = Math.min(points, totalPoints);
                        const currentCenter = constrainedViewRange[0] + Math.floor(windowSize / 2);
                        const newStart = Math.max(0, Math.min(currentCenter - Math.floor(pts / 2), totalPoints - pts));
                        setViewRange([newStart, newStart + pts]);
                      }}
                      disabled={points > totalPoints}
                    >
                      {points.toLocaleString()}
                    </button>
                  ))}
                  <button
                    className="btn"
                    style={{ padding: '0.2rem 0.5rem', fontSize: '0.7rem', marginLeft: 'auto' }}
                    onClick={() => {
                      const endIdx = Math.min(totalPoints, MAX_DISPLAY_POINTS);
                      setViewRange([0, endIdx]);
                    }}
                  >
                    Reset
                  </button>
                </div>
              </div>
            );
          })()}

          {/* Charts Tab */}
          {activeTab === 'charts' && (
            <>
              {visibleOhlcvData && (
                <>
                  <div className="chart-container">
                    <OHLCVChart
                      data={visibleOhlcvData}
                      regimeData={visibleRegimeData}
                      showRegimes={chartSettings.showRegimes}
                      showVolume={chartSettings.showVolume}
                      height={500}
                    />
                  </div>
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
