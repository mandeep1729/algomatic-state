import { useEffect, useState } from 'react';
import api from '../../../api';
import type { RiskPreferences } from '../../../types';

export default function SettingsRisk() {
  const [prefs, setPrefs] = useState<RiskPreferences | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.fetchRiskPreferences().then(setPrefs).finally(() => setLoading(false));
  }, []);

  function updateField<K extends keyof RiskPreferences>(key: K, value: RiskPreferences[K]) {
    setPrefs((prev) => prev ? { ...prev, [key]: value } : prev);
    setSaved(false);
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!prefs) return;
    setError(null);
    setSaving(true);
    try {
      const updated = await api.updateRiskPreferences(prefs);
      setPrefs(updated);
      setSaved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save');
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <div className="p-8 text-[var(--text-secondary)]">Loading...</div>;
  if (!prefs) return null;

  return (
    <div className="p-6">
      <h1 className="mb-6 text-2xl font-semibold">Risk Preferences</h1>

      <form onSubmit={handleSave} className="max-w-2xl space-y-6">
        <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-5 space-y-5">
          {/* Max loss per trade */}
          <NumberField
            label="Max Loss Per Trade (%)"
            value={prefs.max_loss_per_trade_pct}
            onChange={(v) => updateField('max_loss_per_trade_pct', v)}
            step={0.1}
            min={0.1}
            max={100}
            hint="Maximum percentage of account you're willing to lose on a single trade."
          />

          {/* Max daily loss */}
          <NumberField
            label="Max Daily Loss (%)"
            value={prefs.max_daily_loss_pct}
            onChange={(v) => updateField('max_daily_loss_pct', v)}
            step={0.5}
            min={0.5}
            max={100}
            hint="Stop trading for the day if total losses exceed this percentage."
          />

          {/* Max open positions */}
          <NumberField
            label="Max Open Positions"
            value={prefs.max_open_positions}
            onChange={(v) => updateField('max_open_positions', v)}
            step={1}
            min={1}
            max={50}
            hint="Maximum number of concurrent open positions."
          />

          {/* Min risk:reward */}
          <NumberField
            label="Minimum Risk:Reward Ratio"
            value={prefs.risk_reward_minimum}
            onChange={(v) => updateField('risk_reward_minimum', v)}
            step={0.1}
            min={0.5}
            max={10}
            hint="Trades below this R:R will be flagged."
          />

          {/* Stop loss required */}
          <div>
            <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">Stop Loss Required</label>
            <button
              type="button"
              onClick={() => updateField('stop_loss_required', !prefs.stop_loss_required)}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                prefs.stop_loss_required ? 'bg-[var(--accent-blue)]' : 'bg-[var(--border-color)]'
              }`}
            >
              <span
                className={`inline-block h-4 w-4 rounded-full bg-white transition-transform ${
                  prefs.stop_loss_required ? 'translate-x-6' : 'translate-x-1'
                }`}
              />
            </button>
            <p className="mt-1 text-xs text-[var(--text-secondary)]">
              {prefs.stop_loss_required
                ? 'All trades must include a stop loss.'
                : 'Trades without stop loss are allowed (not recommended).'}
            </p>
          </div>
        </div>

        {/* Thresholds preview */}
        <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
          <h3 className="mb-3 text-xs font-medium text-[var(--text-secondary)]">Current Risk Rules</h3>
          <div className="space-y-1 text-sm">
            <div className="flex justify-between">
              <span className="text-[var(--text-secondary)]">Max loss per trade</span>
              <span className="font-mono font-medium">{prefs.max_loss_per_trade_pct}%</span>
            </div>
            <div className="flex justify-between">
              <span className="text-[var(--text-secondary)]">Max daily loss</span>
              <span className="font-mono font-medium">{prefs.max_daily_loss_pct}%</span>
            </div>
            <div className="flex justify-between">
              <span className="text-[var(--text-secondary)]">Max positions</span>
              <span className="font-mono font-medium">{prefs.max_open_positions}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-[var(--text-secondary)]">Min R:R</span>
              <span className="font-mono font-medium">{prefs.risk_reward_minimum}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-[var(--text-secondary)]">Stop loss</span>
              <span className={`text-xs font-medium ${prefs.stop_loss_required ? 'text-[var(--accent-green)]' : 'text-[var(--accent-red)]'}`}>
                {prefs.stop_loss_required ? 'Required' : 'Optional'}
              </span>
            </div>
          </div>
        </div>

        {error && (
          <div className="rounded-md border border-[var(--accent-red)] bg-[var(--accent-red)]/5 px-3 py-2 text-xs text-[var(--accent-red)]">
            {error}
          </div>
        )}
        {saved && (
          <div className="rounded-md border border-[var(--accent-green)] bg-[var(--accent-green)]/5 px-3 py-2 text-xs text-[var(--accent-green)]">
            Risk preferences saved successfully.
          </div>
        )}

        <button
          type="submit"
          disabled={saving}
          className="rounded-md bg-[var(--accent-blue)] px-5 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {saving ? 'Saving...' : 'Save Preferences'}
        </button>
      </form>
    </div>
  );
}

function NumberField({
  label,
  value,
  onChange,
  step,
  min,
  max,
  hint,
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
  step: number;
  min: number;
  max: number;
  hint?: string;
}) {
  return (
    <div>
      <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">{label}</label>
      <input
        type="number"
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value) || 0)}
        step={step}
        min={min}
        max={max}
        className="form-input w-32"
      />
      {hint && <p className="mt-1 text-xs text-[var(--text-secondary)]">{hint}</p>}
    </div>
  );
}
