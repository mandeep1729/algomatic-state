import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import api from '../../api';
import { fetchOHLCVData, fetchFeatures, fetchTickers } from '../../api';
import type { TickerInfo } from '../../api';
import type { OHLCVData, FeatureData } from '../../api/client';
import { OHLCVChart } from '../../../components/OHLCVChart';
import { useChartContext } from '../../context/ChartContext';
import EvaluationDisplay from '../../components/EvaluationDisplay';
import type { EvaluateResponse, TradeDirection } from '../../types';
import { createLogger } from '../../utils/logger';

const log = createLogger('EvaluateIdea');

const TIMEFRAMES = ['15Min', '1Hour', '4Hour', '1Day'] as const;

export default function EvaluateIdea() {
  const [symbol, setSymbol] = useState('');
  const [direction, setDirection] = useState<TradeDirection>('long');
  const [entryPrice, setEntryPrice] = useState<number>(0);
  const [stopLoss, setStopLoss] = useState<number>(0);
  const [targetPrice, setTargetPrice] = useState<number>(0);

  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<EvaluateResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Ticker search state
  const [tickers, setTickers] = useState<TickerInfo[]>([]);
  const [tickerQuery, setTickerQuery] = useState('');
  const [showDropdown, setShowDropdown] = useState(false);
  const [highlightIdx, setHighlightIdx] = useState(-1);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Chart state
  const [chartSymbol, setChartSymbol] = useState<string | null>(null);
  const [chartTimeframe, setChartTimeframe] = useState<string>('1Hour');
  const [ohlcvData, setOhlcvData] = useState<OHLCVData | null>(null);
  const [featureData, setFeatureData] = useState<FeatureData | null>(null);
  const [chartLoading, setChartLoading] = useState(false);
  const [chartError, setChartError] = useState<string | null>(null);

  const { setChartActive, setFeatureNames, selectedFeatures } = useChartContext();

  // Load tickers on mount
  useEffect(() => {
    let cancelled = false;
    fetchTickers()
      .then((data) => {
        if (!cancelled) {
          log.debug(`Loaded ${data.length} tickers`);
          setTickers(data);
        }
      })
      .catch((err) => {
        log.warn('Failed to load tickers', err);
      });
    return () => { cancelled = true; };
  }, []);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setShowDropdown(false);
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  // Filtered tickers for dropdown
  const filteredTickers = useMemo(() => {
    if (!tickerQuery.trim()) return [];
    const q = tickerQuery.toUpperCase().trim();
    return tickers
      .filter((t) => t.symbol.toUpperCase().startsWith(q))
      .slice(0, 20);
  }, [tickers, tickerQuery]);

  // Load chart data
  const loadChart = useCallback(
    async (sym: string, tf: string) => {
      if (!sym.trim()) return;
      const upperSym = sym.toUpperCase().trim();
      log.info(`Loading chart for ${upperSym} @ ${tf}`);
      setChartLoading(true);
      setChartError(null);
      setChartSymbol(upperSym);
      setChartTimeframe(tf);

      try {
        const [ohlcv, features] = await Promise.all([
          fetchOHLCVData(upperSym, tf),
          fetchFeatures(upperSym, tf).catch(() => null),
        ]);
        setOhlcvData(ohlcv);
        setFeatureData(features);
        setChartActive(true);
        if (features) {
          setFeatureNames(features.feature_names);
        }
        log.debug(`Chart loaded: ${ohlcv.timestamps.length} bars`);
      } catch (err) {
        log.error('Failed to load chart data', err);
        setChartError(err instanceof Error ? err.message : 'Failed to load chart');
        setOhlcvData(null);
        setFeatureData(null);
        setChartActive(false);
      } finally {
        setChartLoading(false);
      }
    },
    [setChartActive, setFeatureNames],
  );

  // Cleanup chart context on unmount
  useEffect(() => {
    return () => {
      setChartActive(false);
    };
  }, [setChartActive]);

  function handleTickerSelect(t: TickerInfo) {
    setSymbol(t.symbol);
    setTickerQuery(t.symbol);
    setShowDropdown(false);
    setHighlightIdx(-1);
    loadChart(t.symbol, chartTimeframe);
  }

  function handleSearchKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHighlightIdx((prev) => Math.min(prev + 1, filteredTickers.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlightIdx((prev) => Math.max(prev - 1, 0));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (highlightIdx >= 0 && highlightIdx < filteredTickers.length) {
        handleTickerSelect(filteredTickers[highlightIdx]);
      } else if (tickerQuery.trim()) {
        // Load chart for manually typed symbol
        const upperSym = tickerQuery.toUpperCase().trim();
        setSymbol(upperSym);
        setShowDropdown(false);
        loadChart(upperSym, chartTimeframe);
      }
    } else if (e.key === 'Escape') {
      setShowDropdown(false);
    }
  }

  function handleTimeframeChange(tf: string) {
    if (chartSymbol) {
      loadChart(chartSymbol, tf);
    }
  }

  // Live R:R calculation
  const riskReward = useMemo(() => {
    if (entryPrice <= 0 || stopLoss <= 0 || targetPrice <= 0) return null;

    const riskPerShare =
      direction === 'long'
        ? entryPrice - stopLoss
        : stopLoss - entryPrice;
    const rewardPerShare =
      direction === 'long'
        ? targetPrice - entryPrice
        : entryPrice - targetPrice;

    if (riskPerShare <= 0) return null;

    return {
      rr: rewardPerShare / riskPerShare,
      risk: Math.abs(riskPerShare),
      reward: Math.abs(rewardPerShare),
    };
  }, [entryPrice, stopLoss, targetPrice, direction]);

  function validate(): string | null {
    if (!symbol.trim()) return 'Symbol is required';
    if (entryPrice <= 0) return 'Entry price must be > 0';
    if (stopLoss <= 0) return 'Stop loss must be > 0';
    if (targetPrice <= 0) return 'Target price must be > 0';

    if (direction === 'long') {
      if (stopLoss >= entryPrice) return 'Stop loss must be below entry for a long trade';
      if (targetPrice <= entryPrice) return 'Target must be above entry for a long trade';
    } else {
      if (stopLoss <= entryPrice) return 'Stop loss must be above entry for a short trade';
      if (targetPrice >= entryPrice) return 'Target must be below entry for a short trade';
    }

    return null;
  }

  async function handleEvaluate(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    const validationError = validate();
    if (validationError) {
      setError(validationError);
      return;
    }

    setSubmitting(true);
    setResult(null);

    try {
      const res = await api.evaluateTrade({
        intent: {
          symbol: symbol.toUpperCase().trim(),
          direction,
          timeframe: '15Min',
          entry_price: entryPrice,
          stop_loss: stopLoss,
          profit_target: targetPrice,
        },
        include_context: true,
      });
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Evaluation failed');
    } finally {
      setSubmitting(false);
    }
  }

  function handleReset() {
    setSymbol('');
    setDirection('long');
    setEntryPrice(0);
    setStopLoss(0);
    setTargetPrice(0);
    setResult(null);
    setError(null);
  }

  return (
    <div className="p-6">
      <h1 className="mb-6 text-2xl font-semibold">Evaluate a Trade Idea</h1>

      {/* Ticker search */}
      <div className="relative mb-6" ref={dropdownRef}>
        <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">
          Search Ticker
        </label>
        <input
          ref={inputRef}
          type="text"
          value={tickerQuery}
          onChange={(e) => {
            setTickerQuery(e.target.value);
            setShowDropdown(true);
            setHighlightIdx(-1);
          }}
          onFocus={() => {
            if (tickerQuery.trim()) setShowDropdown(true);
          }}
          onKeyDown={handleSearchKeyDown}
          placeholder="Type a symbol (e.g. AAPL, SPY)..."
          className="form-input w-full max-w-md"
        />
        {showDropdown && filteredTickers.length > 0 && (
          <div className="absolute z-20 mt-1 max-h-64 w-full max-w-md overflow-y-auto rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] shadow-lg">
            {filteredTickers.map((t, idx) => (
              <button
                key={t.symbol}
                type="button"
                onClick={() => handleTickerSelect(t)}
                className={`flex w-full items-center gap-3 px-3 py-2 text-left text-sm transition-colors hover:bg-[var(--bg-tertiary)] ${
                  idx === highlightIdx ? 'bg-[var(--bg-tertiary)]' : ''
                }`}
              >
                <span className="font-medium text-[var(--text-primary)]">{t.symbol}</span>
                {t.name && (
                  <span className="truncate text-xs text-[var(--text-secondary)]">{t.name}</span>
                )}
                {t.exchange && (
                  <span className="ml-auto text-xs text-[var(--text-secondary)]">{t.exchange}</span>
                )}
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="grid gap-8 lg:grid-cols-[400px_1fr]">
        {/* Left column: Input form */}
        <form onSubmit={handleEvaluate} className="space-y-4">
          <div className="space-y-4 rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
            {/* Symbol */}
            <FormField label="Symbol">
              <input
                type="text"
                value={symbol}
                onChange={(e) => setSymbol(e.target.value)}
                placeholder="AAPL"
                className="form-input"
              />
            </FormField>

            {/* Direction */}
            <FormField label="Direction">
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setDirection('long')}
                  className={`flex-1 rounded-md border px-3 py-2 text-sm font-medium transition-colors ${
                    direction === 'long'
                      ? 'border-[var(--accent-green)] bg-[var(--accent-green)]/10 text-[var(--accent-green)]'
                      : 'border-[var(--border-color)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
                  }`}
                >
                  Long
                </button>
                <button
                  type="button"
                  onClick={() => setDirection('short')}
                  className={`flex-1 rounded-md border px-3 py-2 text-sm font-medium transition-colors ${
                    direction === 'short'
                      ? 'border-[var(--accent-red)] bg-[var(--accent-red)]/10 text-[var(--accent-red)]'
                      : 'border-[var(--border-color)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
                  }`}
                >
                  Short
                </button>
              </div>
            </FormField>

            {/* Price inputs */}
            <div className="grid grid-cols-3 gap-3">
              <FormField label="Entry Price">
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={entryPrice || ''}
                  onChange={(e) => setEntryPrice(parseFloat(e.target.value) || 0)}
                  placeholder="0.00"
                  className="form-input"
                />
              </FormField>
              <FormField label="Stop Loss">
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={stopLoss || ''}
                  onChange={(e) => setStopLoss(parseFloat(e.target.value) || 0)}
                  placeholder="0.00"
                  className="form-input"
                />
              </FormField>
              <FormField label="Target">
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={targetPrice || ''}
                  onChange={(e) => setTargetPrice(parseFloat(e.target.value) || 0)}
                  placeholder="0.00"
                  className="form-input"
                />
              </FormField>
            </div>

            {/* Live R:R display */}
            {riskReward && (
              <div className="flex items-center gap-2 text-xs">
                <span className="text-[var(--text-secondary)]">Risk:Reward</span>
                <span
                  className={`font-mono font-medium ${
                    riskReward.rr >= 1.5
                      ? 'text-[var(--accent-green)]'
                      : riskReward.rr >= 1
                        ? 'text-[var(--accent-yellow)]'
                        : 'text-[var(--accent-red)]'
                  }`}
                >
                  {riskReward.rr.toFixed(2)}
                </span>
                <span className="text-[var(--text-secondary)]">
                  (risk ${riskReward.risk.toFixed(2)} / reward ${riskReward.reward.toFixed(2)})
                </span>
              </div>
            )}
          </div>

          {/* Error message */}
          {error && (
            <div className="rounded-md border border-[var(--accent-red)] bg-[var(--accent-red)]/5 px-3 py-2 text-xs text-[var(--accent-red)]">
              {error}
            </div>
          )}

          {/* Actions */}
          <div className="flex gap-3">
            <button
              type="submit"
              disabled={submitting}
              className="rounded-md bg-[var(--accent-blue)] px-5 py-2 text-sm font-medium text-white hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {submitting ? 'Evaluating...' : 'Evaluate'}
            </button>
            {result && (
              <button
                type="button"
                onClick={handleReset}
                className="rounded-md border border-[var(--border-color)] px-4 py-2 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
              >
                New Evaluation
              </button>
            )}
          </div>
        </form>

        {/* Right column: Evaluation results */}
        <div>
          {submitting && (
            <div className="flex items-center gap-3 rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-8 text-sm text-[var(--text-secondary)]">
              <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-[var(--accent-blue)] border-t-transparent" />
              Running evaluation...
            </div>
          )}

          {result && !submitting && (
            <div>
              {/* Intent summary */}
              <div className="mb-4 rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
                <div className="flex flex-wrap items-center gap-3">
                  <span className="text-lg font-semibold">{result.intent.symbol}</span>
                  <span
                    className={`rounded px-2 py-0.5 text-xs font-medium ${
                      result.intent.direction === 'long'
                        ? 'bg-[var(--accent-green)]/10 text-[var(--accent-green)]'
                        : 'bg-[var(--accent-red)]/10 text-[var(--accent-red)]'
                    }`}
                  >
                    {result.intent.direction.toUpperCase()}
                  </span>
                  <span className="text-xs text-[var(--text-secondary)]">
                    R:R {result.intent.risk_reward_ratio.toFixed(2)}
                  </span>
                </div>
                <div className="mt-2 flex gap-4 text-xs text-[var(--text-secondary)]">
                  <span>Entry: ${result.intent.entry_price.toFixed(2)}</span>
                  <span>Stop: ${result.intent.stop_loss.toFixed(2)}</span>
                  <span>Target: ${result.intent.profit_target.toFixed(2)}</span>
                </div>
              </div>

              {/* Full evaluation display */}
              <EvaluationDisplay evaluation={result.evaluation} />
            </div>
          )}

          {!result && !submitting && (
            <div className="flex h-64 items-center justify-center rounded-lg border border-dashed border-[var(--border-color)] bg-[var(--bg-secondary)] text-sm text-[var(--text-secondary)]">
              Fill out the form and click Evaluate to see results here.
            </div>
          )}
        </div>
      </div>

      {/* Chart section — full width below the form/results grid */}
      {(chartSymbol || chartLoading) && (
        <div className="mt-8">
          {/* Timeframe buttons + symbol label */}
          <div className="mb-3 flex items-center gap-3">
            <span className="text-sm font-medium text-[var(--text-primary)]">
              {chartSymbol}
            </span>
            <div className="flex gap-1">
              {TIMEFRAMES.map((tf) => (
                <button
                  key={tf}
                  type="button"
                  onClick={() => handleTimeframeChange(tf)}
                  disabled={chartLoading}
                  className={`rounded-md px-3 py-1 text-xs font-medium transition-colors ${
                    chartTimeframe === tf
                      ? 'bg-[var(--accent-blue)] text-white'
                      : 'border border-[var(--border-color)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
                  } disabled:opacity-50`}
                >
                  {tf}
                </button>
              ))}
            </div>
            {chartLoading && (
              <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-[var(--accent-blue)] border-t-transparent" />
            )}
          </div>

          {/* Chart error */}
          {chartError && (
            <div className="mb-3 rounded-md border border-[var(--accent-red)] bg-[var(--accent-red)]/5 px-3 py-2 text-xs text-[var(--accent-red)]">
              {chartError}
            </div>
          )}

          {/* OHLCV Chart */}
          {ohlcvData && !chartLoading && (
            <div className="rounded-lg border border-[var(--border-color)] overflow-hidden">
              <OHLCVChart
                data={ohlcvData}
                featureData={featureData}
                selectedFeatures={selectedFeatures}
                showVolume={true}
                height={500}
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function FormField({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">
        {label}
      </span>
      {children}
    </label>
  );
}
