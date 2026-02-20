import { useEffect, useMemo, useRef, useState } from 'react';
import { ChevronDown, Search, X } from 'lucide-react';
import type { StrategyDefinition, StrategyCategory, StrategyDirection } from '../../types';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const CATEGORY_OPTIONS: { value: StrategyCategory; label: string }[] = [
  { value: 'trend', label: 'Trend Following' },
  { value: 'mean_reversion', label: 'Mean Reversion' },
  { value: 'breakout', label: 'Breakout' },
  { value: 'volume_flow', label: 'Volume Flow' },
  { value: 'pattern', label: 'Pattern' },
  { value: 'regime', label: 'Regime' },
  { value: 'custom', label: 'Custom' },
];

const DIRECTION_OPTIONS: { value: StrategyDirection; label: string }[] = [
  { value: 'long_short', label: 'Long & Short' },
  { value: 'long_only', label: 'Long Only' },
  { value: 'short_only', label: 'Short Only' },
];

const TIMEFRAME_OPTIONS = ['1Min', '5Min', '15Min', '1Hour', '1Day'];

// ---------------------------------------------------------------------------
// Clone Templates
// ---------------------------------------------------------------------------

export interface CloneTemplate {
  source: 'user' | 'predefined' | 'probe';
  label: string;
  sourceLabel: string;
  data: Partial<StrategyDefinition>;
}

// ---------------------------------------------------------------------------
// Form Data (matches StrategyDefinition minus id/is_predefined/source_strategy_id)
// ---------------------------------------------------------------------------

export interface StrategyFormData {
  name: string;
  display_name: string;
  description: string;
  category: StrategyCategory;
  direction: StrategyDirection;
  entry_long: string | null;
  entry_short: string | null;
  exit_long: string | null;
  required_features: string[] | null;
  tags: string[] | null;
  timeframes: string[];
  max_risk_pct: number;
  min_risk_reward: number;
  atr_stop_mult: number | null;
  atr_target_mult: number | null;
  trailing_atr_mult: number | null;
  time_stop_bars: number | null;
  is_active: boolean;
}

const EMPTY_FORM: StrategyFormData = {
  name: '',
  display_name: '',
  description: '',
  category: 'custom',
  direction: 'long_short',
  entry_long: null,
  entry_short: null,
  exit_long: null,
  required_features: null,
  tags: null,
  timeframes: [],
  max_risk_pct: 2.0,
  min_risk_reward: 1.5,
  atr_stop_mult: null,
  atr_target_mult: null,
  trailing_atr_mult: null,
  time_stop_bars: null,
  is_active: true,
};

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface StrategyFormProps {
  initial?: Partial<StrategyDefinition>;
  onSave: (data: StrategyFormData) => Promise<void>;
  onCancel: () => void;
  isEditing?: boolean;
  cloneTemplates?: CloneTemplate[];
}

// ---------------------------------------------------------------------------
// Clone Dropdown
// ---------------------------------------------------------------------------

function CloneDropdown({
  templates,
  onSelect,
  onClear,
}: {
  templates: CloneTemplate[];
  onSelect: (template: CloneTemplate) => void;
  onClear: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [selectedLabel, setSelectedLabel] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const filtered = useMemo(() => {
    if (!search.trim()) return templates;
    const q = search.toLowerCase();
    return templates.filter(
      (t) => t.label.toLowerCase().includes(q) || t.sourceLabel.toLowerCase().includes(q),
    );
  }, [templates, search]);

  // Group by source
  const grouped = useMemo(() => {
    const groups: Record<string, CloneTemplate[]> = {};
    for (const t of filtered) {
      const key = t.sourceLabel;
      if (!groups[key]) groups[key] = [];
      groups[key].push(t);
    }
    return groups;
  }, [filtered]);

  function handleSelect(t: CloneTemplate) {
    setSelectedLabel(t.label);
    setSearch('');
    setOpen(false);
    onSelect(t);
  }

  function handleClear() {
    setSelectedLabel(null);
    setSearch('');
    onClear();
  }

  return (
    <div ref={containerRef} className="relative">
      <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">
        Clone from Existing
      </label>
      <div className="flex items-center gap-1">
        <button
          type="button"
          onClick={() => setOpen(!open)}
          className="form-input flex h-9 w-full items-center justify-between gap-2 text-left text-sm"
        >
          <span className={selectedLabel ? '' : 'text-[var(--text-secondary)]'}>
            {selectedLabel || 'Start from scratch or clone...'}
          </span>
          <ChevronDown size={14} className="shrink-0 text-[var(--text-secondary)]" />
        </button>
        {selectedLabel && (
          <button
            type="button"
            onClick={handleClear}
            className="rounded p-1 text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-primary)]"
          >
            <X size={14} />
          </button>
        )}
      </div>

      {open && (
        <div className="absolute left-0 right-0 top-full z-50 mt-1 max-h-72 overflow-auto rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] shadow-lg">
          {/* Search */}
          <div className="sticky top-0 border-b border-[var(--border-color)] bg-[var(--bg-secondary)] p-2">
            <div className="relative">
              <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--text-secondary)]" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search strategies..."
                className="form-input h-8 w-full pl-8 text-xs"
                autoFocus
              />
            </div>
          </div>

          {/* Grouped list */}
          {Object.keys(grouped).length === 0 ? (
            <div className="p-3 text-center text-xs text-[var(--text-secondary)]">No strategies found</div>
          ) : (
            Object.entries(grouped).map(([group, items]) => (
              <div key={group}>
                <div className="sticky top-[44px] bg-[var(--bg-primary)] px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
                  {group} ({items.length})
                </div>
                {items.map((t, i) => (
                  <button
                    key={`${group}-${i}`}
                    type="button"
                    onClick={() => handleSelect(t)}
                    className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs hover:bg-[var(--bg-tertiary)]"
                  >
                    <span className="truncate font-medium">{t.label}</span>
                  </button>
                ))}
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Collapsible Section
// ---------------------------------------------------------------------------

function CollapsibleSection({
  title,
  defaultOpen = false,
  children,
}: {
  title: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className="rounded-lg border border-[var(--border-color)]">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="flex w-full items-center justify-between px-3 py-2 text-xs font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
      >
        {title}
        <ChevronDown size={14} className={`transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>
      {isOpen && <div className="border-t border-[var(--border-color)] p-3 space-y-3">{children}</div>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tag Input
// ---------------------------------------------------------------------------

function TagInput({
  value,
  onChange,
  placeholder,
}: {
  value: string[] | null;
  onChange: (v: string[] | null) => void;
  placeholder: string;
}) {
  const [input, setInput] = useState('');

  function addTag() {
    const trimmed = input.trim();
    if (!trimmed) return;
    const current = value || [];
    if (!current.includes(trimmed)) {
      onChange([...current, trimmed]);
    }
    setInput('');
  }

  function removeTag(tag: string) {
    const updated = (value || []).filter((t) => t !== tag);
    onChange(updated.length > 0 ? updated : null);
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault();
      addTag();
    }
  }

  return (
    <div>
      <div className="flex flex-wrap gap-1.5 mb-1.5">
        {(value || []).map((tag) => (
          <span
            key={tag}
            className="inline-flex items-center gap-1 rounded-full bg-[var(--accent-blue)]/10 px-2 py-0.5 text-[11px] font-medium text-[var(--accent-blue)]"
          >
            {tag}
            <button type="button" onClick={() => removeTag(tag)} className="hover:text-[var(--accent-red)]">
              <X size={10} />
            </button>
          </span>
        ))}
      </div>
      <input
        type="text"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        onBlur={addTag}
        placeholder={placeholder}
        className="form-input h-8 w-full text-xs"
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export function StrategyForm({
  initial,
  onSave,
  onCancel,
  isEditing = false,
  cloneTemplates,
}: StrategyFormProps) {
  const [form, setForm] = useState<StrategyFormData>(() => ({
    ...EMPTY_FORM,
    ...initial,
    category: (initial?.category as StrategyCategory) || 'custom',
    direction: (initial?.direction as StrategyDirection) || 'long_short',
    timeframes: initial?.timeframes || [],
    max_risk_pct: initial?.max_risk_pct ?? 2.0,
    min_risk_reward: initial?.min_risk_reward ?? 1.5,
  }));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [touched, setTouched] = useState<Record<string, boolean>>({});

  // ---------------------------------------------------------------------------
  // Validation
  // ---------------------------------------------------------------------------

  const validationErrors = useMemo(() => {
    const errors: Record<string, string> = {};
    if (!form.name.trim()) errors.name = 'Name is required';
    if (!form.display_name.trim()) errors.display_name = 'Display name is required';
    if (form.timeframes.length === 0) errors.timeframes = 'At least one timeframe is required';
    return errors;
  }, [form.name, form.display_name, form.timeframes]);

  const isFormValid = Object.keys(validationErrors).length === 0;

  const missingFieldsSummary = useMemo(() => {
    const missing = Object.values(validationErrors);
    return missing.length > 0 ? missing.join(', ') : '';
  }, [validationErrors]);

  function markTouched(field: string) {
    setTouched((prev) => ({ ...prev, [field]: true }));
  }

  function updateField<K extends keyof StrategyFormData>(key: K, value: StrategyFormData[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function toggleTimeframe(tf: string) {
    markTouched('timeframes');
    setForm((prev) => ({
      ...prev,
      timeframes: prev.timeframes.includes(tf)
        ? prev.timeframes.filter((t) => t !== tf)
        : [...prev.timeframes, tf],
    }));
  }

  function handleCloneSelect(template: CloneTemplate) {
    const d = template.data;
    setForm((prev) => ({
      ...prev,
      name: d.name ? `${d.name}_copy` : prev.name,
      display_name: d.display_name ? `${d.display_name} (Copy)` : prev.display_name,
      description: d.description ?? prev.description,
      category: (d.category as StrategyCategory) ?? prev.category,
      direction: (d.direction as StrategyDirection) ?? prev.direction,
      entry_long: d.entry_long ?? prev.entry_long,
      entry_short: d.entry_short ?? prev.entry_short,
      exit_long: d.exit_long ?? prev.exit_long,
      required_features: d.required_features ?? prev.required_features,
      tags: d.tags ?? prev.tags,
      timeframes: d.timeframes ?? prev.timeframes,
      max_risk_pct: d.max_risk_pct ?? prev.max_risk_pct,
      min_risk_reward: d.min_risk_reward ?? prev.min_risk_reward,
      atr_stop_mult: d.atr_stop_mult ?? prev.atr_stop_mult,
      atr_target_mult: d.atr_target_mult ?? prev.atr_target_mult,
      trailing_atr_mult: d.trailing_atr_mult ?? prev.trailing_atr_mult,
      time_stop_bars: d.time_stop_bars ?? prev.time_stop_bars,
    }));
  }

  function handleCloneClear() {
    setForm({ ...EMPTY_FORM });
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    // Mark all validatable fields as touched so inline errors show
    setTouched({ name: true, display_name: true, timeframes: true });

    if (!isFormValid) {
      setError(missingFieldsSummary);
      return;
    }

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

      {/* Clone dropdown (only in create mode) */}
      {!isEditing && cloneTemplates && cloneTemplates.length > 0 && (
        <CloneDropdown
          templates={cloneTemplates}
          onSelect={handleCloneSelect}
          onClear={handleCloneClear}
        />
      )}

      {/* Section 1: Identity */}
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">
            Name <span className="text-[var(--accent-red)]">*</span>
          </label>
          <input
            type="text"
            value={form.name}
            onChange={(e) => updateField('name', e.target.value)}
            onBlur={() => markTouched('name')}
            className={`form-input h-9 w-full text-sm ${touched.name && validationErrors.name ? 'border-[var(--accent-red)]' : ''}`}
            placeholder="e.g. momentum_pullback"
          />
          {touched.name && validationErrors.name && (
            <p className="mt-1 text-[11px] text-[var(--accent-red)]">{validationErrors.name}</p>
          )}
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">
            Display Name <span className="text-[var(--accent-red)]">*</span>
          </label>
          <input
            type="text"
            value={form.display_name}
            onChange={(e) => updateField('display_name', e.target.value)}
            onBlur={() => markTouched('display_name')}
            className={`form-input h-9 w-full text-sm ${touched.display_name && validationErrors.display_name ? 'border-[var(--accent-red)]' : ''}`}
            placeholder="e.g. Momentum Pullback"
          />
          {touched.display_name && validationErrors.display_name && (
            <p className="mt-1 text-[11px] text-[var(--accent-red)]">{validationErrors.display_name}</p>
          )}
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">Category</label>
          <select
            value={form.category}
            onChange={(e) => updateField('category', e.target.value as StrategyCategory)}
            className="form-input h-9 w-full text-sm"
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

      {/* Section 2: Description & Rules */}
      <div>
        <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">Description / Philosophy</label>
        <textarea
          value={form.description}
          onChange={(e) => updateField('description', e.target.value)}
          rows={2}
          className="form-input w-full resize-none text-sm"
          placeholder="What is the core thesis of this strategy?"
        />
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">Entry Long</label>
          <textarea
            value={form.entry_long || ''}
            onChange={(e) => updateField('entry_long', e.target.value || null)}
            rows={2}
            className="form-input w-full resize-none text-xs"
            placeholder="Conditions for entering a long position..."
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">Entry Short</label>
          <textarea
            value={form.entry_short || ''}
            onChange={(e) => updateField('entry_short', e.target.value || null)}
            rows={2}
            className="form-input w-full resize-none text-xs"
            placeholder="Conditions for entering a short position..."
          />
        </div>
      </div>

      <div>
        <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">Exit Criteria</label>
        <textarea
          value={form.exit_long || ''}
          onChange={(e) => updateField('exit_long', e.target.value || null)}
          rows={2}
          className="form-input w-full resize-none text-xs"
          placeholder="When and how to exit positions..."
        />
      </div>

      {/* Section 3: Timeframes, Indicators, Tags */}
      <div>
        <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">
          Timeframes <span className="text-[var(--accent-red)]">*</span>
        </label>
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
        {touched.timeframes && validationErrors.timeframes && (
          <p className="mt-1 text-[11px] text-[var(--accent-red)]">{validationErrors.timeframes}</p>
        )}
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">Indicators</label>
          <TagInput
            value={form.required_features}
            onChange={(v) => updateField('required_features', v)}
            placeholder="e.g. ema_48, vwap (press Enter)"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">Tags</label>
          <TagInput
            value={form.tags}
            onChange={(v) => updateField('tags', v)}
            placeholder="e.g. pullback, scalp (press Enter)"
          />
        </div>
      </div>

      {/* Section 4: Risk (collapsible) */}
      <CollapsibleSection title="Risk Parameters" defaultOpen>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">Max Risk (%)</label>
            <input
              type="number"
              value={form.max_risk_pct}
              onChange={(e) => updateField('max_risk_pct', parseFloat(e.target.value) || 0)}
              step={0.1}
              min={0.1}
              className="form-input h-8 w-24 text-xs"
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
              className="form-input h-8 w-24 text-xs"
            />
          </div>
        </div>
      </CollapsibleSection>

      {/* Section 5: ATR Exit Parameters (collapsible) */}
      <CollapsibleSection title="ATR Exit Parameters (Optional)">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">ATR Stop Mult</label>
            <input
              type="number"
              value={form.atr_stop_mult ?? ''}
              onChange={(e) => updateField('atr_stop_mult', e.target.value ? parseFloat(e.target.value) : null)}
              step={0.1}
              className="form-input h-8 w-24 text-xs"
              placeholder="e.g. 1.5"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">ATR Target Mult</label>
            <input
              type="number"
              value={form.atr_target_mult ?? ''}
              onChange={(e) => updateField('atr_target_mult', e.target.value ? parseFloat(e.target.value) : null)}
              step={0.1}
              className="form-input h-8 w-24 text-xs"
              placeholder="e.g. 3.0"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">Trailing ATR Mult</label>
            <input
              type="number"
              value={form.trailing_atr_mult ?? ''}
              onChange={(e) => updateField('trailing_atr_mult', e.target.value ? parseFloat(e.target.value) : null)}
              step={0.1}
              className="form-input h-8 w-24 text-xs"
              placeholder="e.g. 2.0"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">Time Stop (bars)</label>
            <input
              type="number"
              value={form.time_stop_bars ?? ''}
              onChange={(e) => updateField('time_stop_bars', e.target.value ? parseInt(e.target.value) : null)}
              min={1}
              className="form-input h-8 w-24 text-xs"
              placeholder="e.g. 20"
            />
          </div>
        </div>
      </CollapsibleSection>

      {/* Error */}
      {error && (
        <div className="rounded-md border border-[var(--accent-red)] bg-[var(--accent-red)]/5 px-3 py-2 text-xs text-[var(--accent-red)]">
          {error}
        </div>
      )}

      {/* Actions */}
      <div className="space-y-2">
        <div className="flex gap-3">
          <button
            type="submit"
            disabled={saving || !isFormValid}
            title={!isFormValid ? missingFieldsSummary : undefined}
            className="rounded-md bg-[var(--accent-blue)] px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
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
        {!isFormValid && (
          <p className="text-[11px] text-[var(--text-secondary)]">
            Fill in all required fields (*) to enable the button
          </p>
        )}
      </div>
    </form>
  );
}
