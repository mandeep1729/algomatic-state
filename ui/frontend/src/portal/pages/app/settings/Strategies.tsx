import { useEffect, useState } from 'react';
import api from '../../../api';
import type { StrategyDefinition, TradeDirection } from '../../../types';

const DIRECTION_OPTIONS: { value: TradeDirection | 'both'; label: string }[] = [
  { value: 'long', label: 'Long' },
  { value: 'short', label: 'Short' },
  { value: 'both', label: 'Both' },
];

const TIMEFRAME_OPTIONS = ['1Min', '5Min', '15Min', '1Hour', '4Hour', '1Day'];

const EMPTY_STRATEGY: Omit<StrategyDefinition, 'id'> = {
  name: '',
  description: '',
  direction: 'both',
  timeframes: [],
  entry_criteria: '',
  exit_criteria: '',
  max_risk_pct: 2.0,
  min_risk_reward: 1.5,
  is_active: true,
};

export default function SettingsStrategies() {
  const [strategies, setStrategies] = useState<StrategyDefinition[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<StrategyDefinition | null>(null);
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    api.fetchStrategies().then(setStrategies).finally(() => setLoading(false));
  }, []);

  function handleEdit(strategy: StrategyDefinition) {
    setCreating(false);
    setEditing({ ...strategy });
  }

  function handleCreate() {
    setEditing(null);
    setCreating(true);
  }

  function handleCancel() {
    setEditing(null);
    setCreating(false);
  }

  async function handleSave(strategy: StrategyDefinition | Omit<StrategyDefinition, 'id'>) {
    if ('id' in strategy) {
      const updated = await api.updateStrategy(strategy.id, strategy);
      setStrategies((prev) => prev.map((s) => (s.id === updated.id ? updated : s)));
      setEditing(null);
    } else {
      const created = await api.createStrategy(strategy);
      setStrategies((prev) => [...prev, created]);
      setCreating(false);
    }
  }

  async function handleToggleActive(strategy: StrategyDefinition) {
    const updated = await api.updateStrategy(strategy.id, { is_active: !strategy.is_active });
    setStrategies((prev) => prev.map((s) => (s.id === updated.id ? updated : s)));
  }

  if (loading) return <div className="p-8 text-[var(--text-secondary)]">Loading...</div>;

  return (
    <div className="p-6">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Strategy Definitions</h1>
        <button
          onClick={handleCreate}
          className="rounded-md bg-[var(--accent-blue)] px-4 py-2 text-sm font-medium text-white hover:opacity-90"
        >
          New Strategy
        </button>
      </div>

      {/* Strategy list */}
      <div className="space-y-4">
        {strategies.map((strategy) => (
          <div key={strategy.id}>
            {editing?.id === strategy.id ? (
              <StrategyForm
                initial={editing}
                onSave={handleSave}
                onCancel={handleCancel}
              />
            ) : (
              <StrategyCard
                strategy={strategy}
                onEdit={() => handleEdit(strategy)}
                onToggle={() => handleToggleActive(strategy)}
              />
            )}
          </div>
        ))}

        {creating && (
          <StrategyForm
            initial={EMPTY_STRATEGY}
            onSave={handleSave}
            onCancel={handleCancel}
          />
        )}

        {strategies.length === 0 && !creating && (
          <div className="rounded-lg border border-dashed border-[var(--border-color)] bg-[var(--bg-secondary)] py-12 text-center text-sm text-[var(--text-secondary)]">
            No strategies defined. Create one to help the system evaluate trades against your plan.
          </div>
        )}
      </div>
    </div>
  );
}

// =============================================================================
// Strategy Card (read view)
// =============================================================================

function StrategyCard({
  strategy,
  onEdit,
  onToggle,
}: {
  strategy: StrategyDefinition;
  onEdit: () => void;
  onToggle: () => void;
}) {
  return (
    <div className={`rounded-lg border bg-[var(--bg-secondary)] p-4 ${
      strategy.is_active ? 'border-[var(--border-color)]' : 'border-[var(--border-color)] opacity-60'
    }`}>
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-medium">{strategy.name}</h3>
            <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${
              strategy.is_active
                ? 'bg-[var(--accent-green)]/10 text-[var(--accent-green)]'
                : 'bg-[var(--bg-primary)] text-[var(--text-secondary)]'
            }`}>
              {strategy.is_active ? 'Active' : 'Inactive'}
            </span>
            <span className="rounded bg-[var(--bg-primary)] px-1.5 py-0.5 text-[10px] text-[var(--text-secondary)]">
              {strategy.direction === 'both' ? 'Long & Short' : strategy.direction.toUpperCase()}
            </span>
          </div>
          <p className="mt-1 text-xs text-[var(--text-secondary)]">{strategy.description}</p>
        </div>
        <div className="flex gap-2">
          <button onClick={onToggle} className="text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)]">
            {strategy.is_active ? 'Deactivate' : 'Activate'}
          </button>
          <button onClick={onEdit} className="text-xs text-[var(--accent-blue)] hover:underline">
            Edit
          </button>
        </div>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-3 text-xs">
        <div>
          <span className="text-[var(--text-secondary)]">Timeframes: </span>
          <span>{strategy.timeframes.join(', ')}</span>
        </div>
        <div>
          <span className="text-[var(--text-secondary)]">Max Risk: </span>
          <span className="font-mono">{strategy.max_risk_pct}%</span>
          <span className="text-[var(--text-secondary)]"> / Min R:R: </span>
          <span className="font-mono">{strategy.min_risk_reward}</span>
        </div>
      </div>

      <div className="mt-2 grid grid-cols-2 gap-3 text-xs">
        <div>
          <span className="text-[var(--text-secondary)]">Entry: </span>
          <span>{strategy.entry_criteria}</span>
        </div>
        <div>
          <span className="text-[var(--text-secondary)]">Exit: </span>
          <span>{strategy.exit_criteria}</span>
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// Strategy Form (create/edit)
// =============================================================================

function StrategyForm({
  initial,
  onSave,
  onCancel,
}: {
  initial: StrategyDefinition | Omit<StrategyDefinition, 'id'>;
  onSave: (strategy: StrategyDefinition | Omit<StrategyDefinition, 'id'>) => Promise<void>;
  onCancel: () => void;
}) {
  const [form, setForm] = useState(initial);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const isEditing = 'id' in initial;

  function updateField<K extends keyof typeof form>(key: K, value: (typeof form)[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function toggleTimeframe(tf: string) {
    setForm((prev) => ({
      ...prev,
      timeframes: prev.timeframes.includes(tf)
        ? prev.timeframes.filter((t) => t !== tf)
        : [...prev.timeframes, tf],
    }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (!form.name.trim()) { setError('Name is required'); return; }
    if (form.timeframes.length === 0) { setError('Select at least one timeframe'); return; }

    setSaving(true);
    try {
      await onSave(form);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save');
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="rounded-lg border border-[var(--accent-blue)]/30 bg-[var(--bg-secondary)] p-4 space-y-4">
      <h3 className="text-sm font-medium">{isEditing ? 'Edit Strategy' : 'New Strategy'}</h3>

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">Name</label>
          <input
            type="text"
            value={form.name}
            onChange={(e) => updateField('name', e.target.value)}
            className="form-input"
            placeholder="e.g. Momentum Pullback Long"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">Direction</label>
          <div className="flex gap-2">
            {DIRECTION_OPTIONS.map((d) => (
              <button
                key={d.value}
                type="button"
                onClick={() => updateField('direction', d.value)}
                className={`flex-1 rounded-md border px-2 py-1.5 text-xs font-medium transition-colors ${
                  form.direction === d.value
                    ? 'border-[var(--accent-blue)] bg-[var(--accent-blue)]/10 text-[var(--accent-blue)]'
                    : 'border-[var(--border-color)] text-[var(--text-secondary)]'
                }`}
              >
                {d.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div>
        <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">Description</label>
        <textarea
          value={form.description}
          onChange={(e) => updateField('description', e.target.value)}
          rows={2}
          className="form-input resize-none"
          placeholder="Brief description of this strategy..."
        />
      </div>

      <div>
        <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">Timeframes</label>
        <div className="flex flex-wrap gap-1.5">
          {TIMEFRAME_OPTIONS.map((tf) => (
            <button
              key={tf}
              type="button"
              onClick={() => toggleTimeframe(tf)}
              className={`rounded-full border px-2.5 py-1 text-xs transition-colors ${
                form.timeframes.includes(tf)
                  ? 'border-[var(--accent-blue)] bg-[var(--accent-blue)]/10 text-[var(--accent-blue)]'
                  : 'border-[var(--border-color)] text-[var(--text-secondary)]'
              }`}
            >
              {tf}
            </button>
          ))}
        </div>
      </div>

      <div>
        <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">Entry Criteria</label>
        <textarea
          value={form.entry_criteria}
          onChange={(e) => updateField('entry_criteria', e.target.value)}
          rows={2}
          className="form-input resize-none"
          placeholder="Describe the conditions for entering a trade..."
        />
      </div>

      <div>
        <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">Exit Criteria</label>
        <textarea
          value={form.exit_criteria}
          onChange={(e) => updateField('exit_criteria', e.target.value)}
          rows={2}
          className="form-input resize-none"
          placeholder="Describe the conditions for exiting..."
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">Max Risk (%)</label>
          <input
            type="number"
            value={form.max_risk_pct}
            onChange={(e) => updateField('max_risk_pct', parseFloat(e.target.value) || 0)}
            step={0.1}
            min={0.1}
            className="form-input w-24"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">Min R:R</label>
          <input
            type="number"
            value={form.min_risk_reward}
            onChange={(e) => updateField('min_risk_reward', parseFloat(e.target.value) || 0)}
            step={0.1}
            min={0.5}
            className="form-input w-24"
          />
        </div>
      </div>

      {error && (
        <div className="rounded-md border border-[var(--accent-red)] bg-[var(--accent-red)]/5 px-3 py-2 text-xs text-[var(--accent-red)]">
          {error}
        </div>
      )}

      <div className="flex gap-3">
        <button
          type="submit"
          disabled={saving}
          className="rounded-md bg-[var(--accent-blue)] px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
        >
          {saving ? 'Saving...' : isEditing ? 'Save Changes' : 'Create Strategy'}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="rounded-md border border-[var(--border-color)] px-4 py-2 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}
