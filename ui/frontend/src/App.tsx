import { useState, useEffect, useCallback, useMemo } from 'react';
import Plot from 'react-plotly.js';
import type { Data, Layout } from 'plotly.js';
import {
  fetchTickers,
  fetchTickerSummary,
  fetchOHLCVData,
  fetchFeatures,
  fetchStatistics,
  fetchRegimes,
  analyzeSymbol,
} from './api';
import type { AnalyzeResponse } from './api';
import type { TickerSummary } from './api';
import type {
  Ticker,
  OHLCVData,
  FeatureData,
  Statistics,
  ChartSettings,
  RegimeData,
} from './types';
import { OHLCVChart, FeatureFilter } from './components';

// Constants
const MAX_DISPLAY_POINTS = 7200;

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
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzeResult, setAnalyzeResult] = useState<AnalyzeResponse | null>(null);

  // Chart settings
  const [chartSettings, setChartSettings] = useState<ChartSettings>({
    showVolume: true,
    showStates: true,
    selectedFeatures: [],
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
    return {
      timestamps: regimeData.timestamps.slice(start, end),
      state_ids: regimeData.state_ids.slice(start, end),
      state_info: regimeData.state_info,
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

      // Load statistics
      const stats = await fetchStatistics(ticker, tf, start, end);
      setStatistics(stats);

      // Load regimes (if model is available)
      try {
        const regimes = await fetchRegimes(ticker, tf, undefined, start, end);
        setRegimeData(regimes);
      } catch (regimeErr) {
        // Regime data is optional - model may not be trained yet
        console.warn('Regimes not available:', regimeErr);
        setRegimeData(null);
      }

      // Refresh ticker summary to get updated bar counts after fetch
      const updatedSummary = await fetchTickerSummary(ticker);
      setTickerSummary(updatedSummary);
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to load data';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  }, []);

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

  const toggleFeature = (feature: string) => {
    setChartSettings((prev) => ({
      ...prev,
      selectedFeatures: prev.selectedFeatures.includes(feature)
        ? prev.selectedFeatures.filter((f) => f !== feature)
        : [...prev.selectedFeatures, feature],
    }));
  };

  // Handle Analyze button click
  const handleAnalyze = async () => {
    if (!selectedTicker) return;

    setAnalyzing(true);
    setAnalyzeResult(null);
    setError(null);

    try {
      const result = await analyzeSymbol(selectedTicker, timeframe);
      setAnalyzeResult(result);

      // Reload data to show updated states
      if (tickerSummary) {
        const tfData = tickerSummary.timeframes[timeframe];
        if (tfData && tfData.earliest && tfData.latest) {
          const start = tfData.earliest.split('T')[0];
          const end = tfData.latest.split('T')[0];
          await loadDataWithParams(selectedTicker, timeframe, start, end);
        }
      }
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Analysis failed';
      setError(errorMessage);
    } finally {
      setAnalyzing(false);
    }
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

            {/* Analyze Button */}
            <button
              onClick={handleAnalyze}
              disabled={!selectedTicker || loading || analyzing}
              style={{
                width: '100%',
                padding: '0.75rem 1rem',
                marginTop: '1rem',
                backgroundColor: analyzing ? '#30363d' : '#238636',
                color: '#fff',
                border: 'none',
                borderRadius: '6px',
                fontSize: '0.875rem',
                fontWeight: 500,
                cursor: !selectedTicker || loading || analyzing ? 'not-allowed' : 'pointer',
                opacity: !selectedTicker || loading || analyzing ? 0.6 : 1,
                transition: 'background-color 0.2s',
              }}
              onMouseOver={(e) => {
                if (!analyzing && selectedTicker && !loading) {
                  e.currentTarget.style.backgroundColor = '#2ea043';
                }
              }}
              onMouseOut={(e) => {
                if (!analyzing) {
                  e.currentTarget.style.backgroundColor = '#238636';
                }
              }}
            >
              {analyzing ? 'Analyzing...' : 'Analyze'}
            </button>

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

            {/* Analyze Result */}
            {analyzeResult && (
              <div style={{
                marginTop: '0.75rem',
                padding: '0.75rem',
                backgroundColor: '#0d1117',
                borderRadius: '6px',
                border: '1px solid #238636',
                fontSize: '0.75rem',
              }}>
                <div style={{ color: '#3fb950', fontWeight: 500, marginBottom: '0.5rem' }}>
                  Analysis Complete
                </div>
                <div style={{ color: '#8b949e' }}>
                  <div>Features: {analyzeResult.features_computed.toLocaleString()}</div>
                  <div>Model: {analyzeResult.model_trained ? 'Trained' : 'Using existing'}</div>
                  <div>States: {analyzeResult.states_computed.toLocaleString()} / {analyzeResult.total_bars.toLocaleString()}</div>
                </div>
              </div>
            )}
          </div>

          {/* Feature Filter */}
          {featureData && (
            <div className="section">
              <FeatureFilter
                selectedFeatures={chartSettings.selectedFeatures}
                availableFeatures={featureData.feature_names}
                onFeatureToggle={toggleFeature}
              />
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

              </div>
            );
          })()}

          {/* Charts Tab */}
          {activeTab === 'charts' && (
            <>
              {visibleOhlcvData && (
                <div className="chart-container">
                  <OHLCVChart
                    data={visibleOhlcvData}
                    featureData={visibleFeatureData}
                    regimeData={visibleRegimeData}
                    selectedFeatures={chartSettings.selectedFeatures}
                    showVolume={chartSettings.showVolume}
                    showStates={chartSettings.showStates}
                    height={500}
                  />
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
