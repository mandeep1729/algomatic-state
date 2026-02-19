import { useState } from 'react';
import { Plus, Loader2 } from 'lucide-react';
import { createAgentStrategy } from '../../api';
import type { AgentStrategy } from '../../types';

const CATEGORY_OPTIONS = [
  { value: 'trend', label: 'Trend Following' },
  { value: 'mean_reversion', label: 'Mean Reversion' },
  { value: 'breakout', label: 'Breakout' },
  { value: 'volume_flow', label: 'Volume Flow' },
  { value: 'pattern', label: 'Pattern' },
  { value: 'regime', label: 'Regime' },
  { value: 'custom', label: 'Custom' },
];

const DIRECTION_OPTIONS = [
  { value: 'long_short', label: 'Long & Short' },
  { value: 'long_only', label: 'Long Only' },
  { value: 'short_only', label: 'Short Only' },
];

interface StrategyPickerProps {
  strategies: AgentStrategy[];
  selectedId: number | null;
  onSelect: (id: number) => void;
  onStrategyCreated: (strategy: AgentStrategy) => void;
}

export function StrategyPicker({ strategies, selectedId, onSelect, onStrategyCreated }: StrategyPickerProps) {
  const [creatingNew, setCreatingNew] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Inline create form state
  const [formName, setFormName] = useState('');
  const [formDisplayName, setFormDisplayName] = useState('');
  const [formDescription, setFormDescription] = useState('');
  const [formCategory, setFormCategory] = useState('custom');
  const [formDirection, setFormDirection] = useState('long_short');

  function resetForm() {
    setFormName('');
    setFormDisplayName('');
    setFormDescription('');
    setFormCategory('custom');
    setFormDirection('long_short');
    setError(null);
  }

  function handleCancelCreate() {
    setCreatingNew(false);
    resetForm();
  }

  async function handleCreateStrategy() {
    const name = formName.trim();
    const displayName = formDisplayName.trim();

    if (!name) {
      setError('Name is required');
      return;
    }
    if (!displayName) {
      setError('Display name is required');
      return;
    }

    setError(null);
    setSaving(true);
    try {
      const created = await createAgentStrategy({
        name,
        display_name: displayName,
        description: formDescription.trim() || null,
        category: formCategory,
        direction: formDirection,
      });
      onStrategyCreated(created);
      onSelect(created.id);
      setCreatingNew(false);
      resetForm();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create strategy');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-3">
      {/* Strategy dropdown */}
      <div>
        <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">Strategy</label>
        <select
          value={selectedId ?? ''}
          onChange={(e) => {
            const val = e.target.value;
            if (val) onSelect(Number(val));
          }}
          className="form-input h-9 w-full text-sm"
        >
          <option value="" disabled>-- Select a strategy --</option>
          {strategies.map((s) => (
            <option key={s.id} value={s.id}>
              {s.display_name || s.name}
            </option>
          ))}
        </select>
      </div>

      {/* Create new strategy button / form */}
      {!creatingNew ? (
        <button
          type="button"
          onClick={() => setCreatingNew(true)}
          className="inline-flex items-center gap-1.5 text-xs font-medium text-[var(--accent-blue)] hover:underline"
        >
          <Plus size={14} />
          Create New Strategy
        </button>
      ) : (
        <div className="rounded-lg border border-[var(--accent-blue)]/30 bg-[var(--bg-secondary)] p-4 space-y-3">
          <h4 className="text-sm font-medium text-[var(--text-primary)]">New Strategy</h4>

          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">Name</label>
              <input
                type="text"
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                placeholder="e.g. momentum_pullback"
                className="form-input h-8 w-full text-xs"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">Display Name</label>
              <input
                type="text"
                value={formDisplayName}
                onChange={(e) => setFormDisplayName(e.target.value)}
                placeholder="e.g. Momentum Pullback"
                className="form-input h-8 w-full text-xs"
              />
            </div>
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">Description</label>
            <textarea
              value={formDescription}
              onChange={(e) => setFormDescription(e.target.value)}
              rows={2}
              placeholder="Brief description of this strategy..."
              className="form-input w-full resize-none text-xs"
            />
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">Category</label>
              <select
                value={formCategory}
                onChange={(e) => setFormCategory(e.target.value)}
                className="form-input h-8 w-full text-xs"
              >
                {CATEGORY_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">Direction</label>
              <div className="flex gap-1.5">
                {DIRECTION_OPTIONS.map((d) => (
                  <button
                    key={d.value}
                    type="button"
                    onClick={() => setFormDirection(d.value)}
                    className={`flex-1 rounded-md border px-1.5 py-1.5 text-[11px] font-medium transition-colors ${
                      formDirection === d.value
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

          {error && (
            <p className="text-xs text-[var(--accent-red)]">{error}</p>
          )}

          <div className="flex gap-2">
            <button
              type="button"
              onClick={handleCreateStrategy}
              disabled={saving}
              className="inline-flex h-8 items-center gap-1.5 rounded-md bg-[var(--accent-blue)] px-4 text-xs font-medium text-white transition-colors hover:bg-[var(--accent-blue)]/90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {saving && <Loader2 size={12} className="animate-spin" />}
              Create
            </button>
            <button
              type="button"
              onClick={handleCancelCreate}
              disabled={saving}
              className="inline-flex h-8 items-center rounded-md border border-[var(--border-color)] px-4 text-xs text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-primary)]"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
