import { useEffect, useState } from 'react';
import api from '../../../api';
import type { EvaluationControls as EvaluationControlsType, Severity } from '../../../types';

const EVALUATOR_LABELS: Record<string, string> = {
  regime_fit: 'Regime Fit',
  entry_timing: 'Entry Timing',
  exit_logic: 'Exit Logic',
  risk_positioning: 'Risk Positioning',
  behavioral: 'Behavioral Signals',
  strategy_consistency: 'Strategy Consistency',
};

const EVALUATOR_DESCRIPTIONS: Record<string, string> = {
  regime_fit: 'Checks whether the trade direction aligns with the current market regime.',
  entry_timing: 'Evaluates whether the entry timing is appropriate given recent price action.',
  exit_logic: 'Reviews stop loss and profit target placement relative to support/resistance.',
  risk_positioning: 'Validates position sizing, risk per trade, and risk:reward ratio.',
  behavioral: 'Detects behavioral patterns like revenge trading, FOMO, or overconfidence.',
  strategy_consistency: 'Checks if the trade matches your declared strategy definitions.',
};

const SEVERITY_OPTIONS: { value: Severity; label: string; description: string }[] = [
  { value: 'info', label: 'Info', description: 'Show all findings including informational.' },
  { value: 'warning', label: 'Warning', description: 'Show warnings, critical, and blockers.' },
  { value: 'critical', label: 'Critical', description: 'Only show critical issues and blockers.' },
  { value: 'blocker', label: 'Blocker', description: 'Only show trade blockers.' },
];

export default function EvaluationControls() {
  const [controls, setControls] = useState<EvaluationControlsType | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.fetchEvaluationControls().then(setControls).finally(() => setLoading(false));
  }, []);

  function toggleEvaluator(key: string) {
    setControls((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        evaluators_enabled: {
          ...prev.evaluators_enabled,
          [key]: !prev.evaluators_enabled[key],
        },
      };
    });
    setSaved(false);
  }

  function toggleBool(key: 'auto_evaluate_synced' | 'notification_on_blocker') {
    setControls((prev) => prev ? { ...prev, [key]: !prev[key] } : prev);
    setSaved(false);
  }

  function setSeverity(value: Severity) {
    setControls((prev) => prev ? { ...prev, severity_threshold: value } : prev);
    setSaved(false);
  }

  async function handleSave() {
    if (!controls) return;
    setError(null);
    setSaving(true);
    try {
      const updated = await api.updateEvaluationControls(controls);
      setControls(updated);
      setSaved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save');
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <div className="p-8 text-[var(--text-secondary)]">Loading...</div>;
  if (!controls) return null;

  const enabledCount = Object.values(controls.evaluators_enabled).filter(Boolean).length;
  const totalCount = Object.keys(controls.evaluators_enabled).length;

  return (
    <div className="p-6">
      <h1 className="mb-6 text-2xl font-semibold">Evaluation Controls</h1>

      <div className="max-w-2xl space-y-6">
        {/* Evaluators */}
        <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-5">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-sm font-medium">Evaluators</h2>
            <span className="text-xs text-[var(--text-secondary)]">{enabledCount}/{totalCount} enabled</span>
          </div>
          <div className="space-y-3">
            {Object.entries(controls.evaluators_enabled).map(([key, enabled]) => (
              <div key={key} className="flex items-start justify-between gap-4">
                <div className="flex-1">
                  <div className="text-sm font-medium">{EVALUATOR_LABELS[key] ?? key}</div>
                  <div className="mt-0.5 text-xs text-[var(--text-secondary)]">{EVALUATOR_DESCRIPTIONS[key]}</div>
                </div>
                <button
                  type="button"
                  onClick={() => toggleEvaluator(key)}
                  className={`relative mt-0.5 inline-flex h-6 w-11 flex-shrink-0 items-center rounded-full transition-colors ${
                    enabled ? 'bg-[var(--accent-blue)]' : 'bg-[var(--border-color)]'
                  }`}
                >
                  <span
                    className={`inline-block h-4 w-4 rounded-full bg-white transition-transform ${
                      enabled ? 'translate-x-6' : 'translate-x-1'
                    }`}
                  />
                </button>
              </div>
            ))}
          </div>
        </div>

        {/* Severity threshold */}
        <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-5">
          <h2 className="mb-3 text-sm font-medium">Notification Severity Threshold</h2>
          <p className="mb-3 text-xs text-[var(--text-secondary)]">
            Only show evaluation findings at or above this severity level.
          </p>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {SEVERITY_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => setSeverity(opt.value)}
                className={`rounded-md border p-2 text-center transition-colors ${
                  controls.severity_threshold === opt.value
                    ? 'border-[var(--accent-blue)] bg-[var(--accent-blue)]/10 text-[var(--accent-blue)]'
                    : 'border-[var(--border-color)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
                }`}
              >
                <div className="text-xs font-medium">{opt.label}</div>
              </button>
            ))}
          </div>
        </div>

        {/* Auto-evaluate and notifications */}
        <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-5 space-y-4">
          <h2 className="text-sm font-medium">Automation</h2>

          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm">Auto-evaluate synced trades</div>
              <div className="text-xs text-[var(--text-secondary)]">Automatically run evaluations on trades synced from your broker.</div>
            </div>
            <button
              type="button"
              onClick={() => toggleBool('auto_evaluate_synced')}
              className={`relative inline-flex h-6 w-11 flex-shrink-0 items-center rounded-full transition-colors ${
                controls.auto_evaluate_synced ? 'bg-[var(--accent-blue)]' : 'bg-[var(--border-color)]'
              }`}
            >
              <span
                className={`inline-block h-4 w-4 rounded-full bg-white transition-transform ${
                  controls.auto_evaluate_synced ? 'translate-x-6' : 'translate-x-1'
                }`}
              />
            </button>
          </div>

          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm">Notify on blockers</div>
              <div className="text-xs text-[var(--text-secondary)]">Get a notification when an evaluation contains blocker-level issues.</div>
            </div>
            <button
              type="button"
              onClick={() => toggleBool('notification_on_blocker')}
              className={`relative inline-flex h-6 w-11 flex-shrink-0 items-center rounded-full transition-colors ${
                controls.notification_on_blocker ? 'bg-[var(--accent-blue)]' : 'bg-[var(--border-color)]'
              }`}
            >
              <span
                className={`inline-block h-4 w-4 rounded-full bg-white transition-transform ${
                  controls.notification_on_blocker ? 'translate-x-6' : 'translate-x-1'
                }`}
              />
            </button>
          </div>
        </div>

        {/* Save */}
        {error && (
          <div className="rounded-md border border-[var(--accent-red)] bg-[var(--accent-red)]/5 px-3 py-2 text-xs text-[var(--accent-red)]">
            {error}
          </div>
        )}
        {saved && (
          <div className="rounded-md border border-[var(--accent-green)] bg-[var(--accent-green)]/5 px-3 py-2 text-xs text-[var(--accent-green)]">
            Evaluation controls saved successfully.
          </div>
        )}

        <button
          onClick={handleSave}
          disabled={saving}
          className="rounded-md bg-[var(--accent-blue)] px-5 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {saving ? 'Saving...' : 'Save Controls'}
        </button>
      </div>
    </div>
  );
}
