import { useState } from 'react';
import api from '../../api';
import type { TradeIntentCreate, EvaluateResponse } from '../../types';
import EvaluationDisplay from '../../components/EvaluationDisplay';

const TIMEFRAME_OPTIONS = ['1Min', '5Min', '15Min', '1Hour', '1Day'];

const INITIAL_FORM: TradeIntentCreate = {
  symbol: '',
  direction: 'long',
  timeframe: '5Min',
  entry_price: 0,
  stop_loss: 0,
  profit_target: 0,
  position_size: undefined,
  rationale: '',
};

export default function Evaluate() {
  const [form, setForm] = useState<TradeIntentCreate>({ ...INITIAL_FORM });
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<EvaluateResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  function updateField<K extends keyof TradeIntentCreate>(key: K, value: TradeIntentCreate[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function validate(): string | null {
    if (!form.symbol.trim()) return 'Symbol is required';
    if (form.entry_price <= 0) return 'Entry price must be > 0';
    if (form.stop_loss <= 0) return 'Stop loss must be > 0';
    if (form.profit_target <= 0) return 'Profit target must be > 0';

    if (form.direction === 'long') {
      if (form.stop_loss >= form.entry_price) return 'Stop loss must be below entry for a long trade';
      if (form.profit_target <= form.entry_price) return 'Profit target must be above entry for a long trade';
    } else {
      if (form.stop_loss <= form.entry_price) return 'Stop loss must be above entry for a short trade';
      if (form.profit_target >= form.entry_price) return 'Profit target must be below entry for a short trade';
    }

    return null;
  }

  async function handleSubmit(e: React.FormEvent) {
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
          ...form,
          symbol: form.symbol.toUpperCase().trim(),
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
    setForm({ ...INITIAL_FORM });
    setResult(null);
    setError(null);
  }

  // Compute R:R for preview
  const riskPerShare = form.direction === 'long'
    ? form.entry_price - form.stop_loss
    : form.stop_loss - form.entry_price;
  const rewardPerShare = form.direction === 'long'
    ? form.profit_target - form.entry_price
    : form.entry_price - form.profit_target;
  const rr = riskPerShare > 0 ? rewardPerShare / riskPerShare : 0;
  const showRR = form.entry_price > 0 && form.stop_loss > 0 && form.profit_target > 0 && riskPerShare > 0;

  return (
    <div className="p-6">
      <h1 className="mb-6 text-2xl font-semibold">Evaluate a Trade</h1>

      <div className="grid gap-8 lg:grid-cols-[400px_1fr]">
        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4 space-y-4">
            {/* Symbol */}
            <FormField label="Symbol">
              <input
                type="text"
                value={form.symbol}
                onChange={(e) => updateField('symbol', e.target.value)}
                placeholder="AAPL"
                className="form-input"
              />
            </FormField>

            {/* Direction */}
            <FormField label="Direction">
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => updateField('direction', 'long')}
                  className={`flex-1 rounded-md border px-3 py-2 text-sm font-medium transition-colors ${
                    form.direction === 'long'
                      ? 'border-[var(--accent-green)] bg-[var(--accent-green)]/10 text-[var(--accent-green)]'
                      : 'border-[var(--border-color)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
                  }`}
                >
                  Long
                </button>
                <button
                  type="button"
                  onClick={() => updateField('direction', 'short')}
                  className={`flex-1 rounded-md border px-3 py-2 text-sm font-medium transition-colors ${
                    form.direction === 'short'
                      ? 'border-[var(--accent-red)] bg-[var(--accent-red)]/10 text-[var(--accent-red)]'
                      : 'border-[var(--border-color)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
                  }`}
                >
                  Short
                </button>
              </div>
            </FormField>

            {/* Timeframe */}
            <FormField label="Timeframe">
              <select
                value={form.timeframe}
                onChange={(e) => updateField('timeframe', e.target.value)}
                className="form-input"
              >
                {TIMEFRAME_OPTIONS.map((tf) => (
                  <option key={tf} value={tf}>{tf}</option>
                ))}
              </select>
            </FormField>

            {/* Prices row */}
            <div className="grid grid-cols-3 gap-3">
              <FormField label="Entry Price">
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={form.entry_price || ''}
                  onChange={(e) => updateField('entry_price', parseFloat(e.target.value) || 0)}
                  placeholder="0.00"
                  className="form-input"
                />
              </FormField>
              <FormField label="Stop Loss">
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={form.stop_loss || ''}
                  onChange={(e) => updateField('stop_loss', parseFloat(e.target.value) || 0)}
                  placeholder="0.00"
                  className="form-input"
                />
              </FormField>
              <FormField label="Target">
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={form.profit_target || ''}
                  onChange={(e) => updateField('profit_target', parseFloat(e.target.value) || 0)}
                  placeholder="0.00"
                  className="form-input"
                />
              </FormField>
            </div>

            {/* R:R preview */}
            {showRR && (
              <div className="flex items-center gap-2 text-xs">
                <span className="text-[var(--text-secondary)]">Risk:Reward</span>
                <span className={`font-mono font-medium ${rr >= 1.5 ? 'text-[var(--accent-green)]' : rr >= 1 ? 'text-[var(--accent-yellow)]' : 'text-[var(--accent-red)]'}`}>
                  {rr.toFixed(2)}
                </span>
                <span className="text-[var(--text-secondary)]">
                  (risk ${Math.abs(riskPerShare).toFixed(2)} / reward ${Math.abs(rewardPerShare).toFixed(2)})
                </span>
              </div>
            )}

            {/* Position size */}
            <FormField label="Position Size (shares)" optional>
              <input
                type="number"
                min="0"
                value={form.position_size ?? ''}
                onChange={(e) => updateField('position_size', e.target.value ? parseInt(e.target.value, 10) : undefined)}
                placeholder="Optional"
                className="form-input"
              />
            </FormField>

            {/* Rationale */}
            <FormField label="Rationale" optional>
              <textarea
                value={form.rationale ?? ''}
                onChange={(e) => updateField('rationale', e.target.value)}
                placeholder="Why are you taking this trade?"
                rows={3}
                className="form-input resize-none"
              />
            </FormField>
          </div>

          {/* Error */}
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
              className="rounded-md bg-[var(--accent-blue)] px-5 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
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

        {/* Result panel */}
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
                  <span className={`rounded px-2 py-0.5 text-xs font-medium ${
                    result.intent.direction === 'long'
                      ? 'bg-[var(--accent-green)]/10 text-[var(--accent-green)]'
                      : 'bg-[var(--accent-red)]/10 text-[var(--accent-red)]'
                  }`}>
                    {result.intent.direction.toUpperCase()}
                  </span>
                  <span className="text-xs text-[var(--text-secondary)]">{result.intent.timeframe}</span>
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

              {/* Evaluation display */}
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
    </div>
  );
}

function FormField({ label, optional, children }: { label: string; optional?: boolean; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">
        {label}
        {optional && <span className="ml-1 font-normal opacity-60">(optional)</span>}
      </span>
      {children}
    </label>
  );
}
