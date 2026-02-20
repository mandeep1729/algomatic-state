import { useEffect, useState } from 'react';
import api, { fetchAgentStrategies, fetchAllProbeStrategies } from '../../../api';
import type { StrategyDefinition, StrategyCategory, StrategyDirection, AgentStrategy } from '../../../types';
import { StrategyForm, type CloneTemplate, type StrategyFormData } from '../../../components/strategies/StrategyForm';
import { parseConditions, conditionsToText } from '../../../components/strategies/conditionUtils';

const CATEGORY_LABELS: Record<string, string> = {
  trend: 'Trend',
  mean_reversion: 'Mean Rev',
  breakout: 'Breakout',
  volume_flow: 'Vol Flow',
  pattern: 'Pattern',
  regime: 'Regime',
  custom: 'Custom',
};

const DIRECTION_LABELS: Record<string, string> = {
  long_short: 'Long & Short',
  long_only: 'Long Only',
  short_only: 'Short Only',
};

export default function SettingsStrategies() {
  const [strategies, setStrategies] = useState<StrategyDefinition[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<StrategyDefinition | null>(null);
  const [creating, setCreating] = useState(false);
  const [cloneTemplates, setCloneTemplates] = useState<CloneTemplate[]>([]);

  useEffect(() => {
    api.fetchStrategies().then(setStrategies).finally(() => setLoading(false));
  }, []);

  // Load clone templates when creating
  useEffect(() => {
    if (!creating) return;
    let cancelled = false;

    async function loadTemplates() {
      const templates: CloneTemplate[] = [];

      try {
        const agentStrategies: AgentStrategy[] = await fetchAgentStrategies();
        for (const s of agentStrategies) {
          templates.push({
            source: s.is_predefined ? 'predefined' : 'user',
            label: s.display_name || s.name,
            sourceLabel: s.is_predefined ? 'Predefined Strategies' : 'My Strategies',
            data: {
              name: s.name,
              display_name: s.display_name,
              description: s.description || '',
              category: s.category as StrategyCategory,
              direction: s.direction as StrategyDirection,
              entry_long: s.entry_long,
              entry_short: s.entry_short,
              exit_long: s.exit_long,
              exit_short: s.exit_short,
              required_features: s.required_features,
              tags: s.tags,
              timeframes: s.timeframes || [],
              max_risk_pct: s.max_risk_pct ?? 2.0,
              min_risk_reward: s.min_risk_reward ?? 1.5,
              atr_stop_mult: s.atr_stop_mult,
              atr_target_mult: s.atr_target_mult,
              trailing_atr_mult: s.trailing_atr_mult,
              time_stop_bars: s.time_stop_bars,
            },
          });
        }
      } catch {
        // Agent strategies may not be available in mock mode
      }

      try {
        const probeResp = await fetchAllProbeStrategies();
        for (const s of probeResp.strategies) {
          templates.push({
            source: 'probe',
            label: s.display_name || s.name,
            sourceLabel: 'Strategy Probe',
            data: mapProbeToFormData(s),
          });
        }
      } catch {
        // Probe endpoint may not be available
      }

      if (!cancelled) setCloneTemplates(templates);
    }

    loadTemplates();
    return () => { cancelled = true; };
  }, [creating]);

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

  async function handleSaveNew(data: StrategyFormData) {
    const created = await api.createStrategy(data as Omit<StrategyDefinition, 'id'>);
    setStrategies((prev) => [...prev, created]);
    setCreating(false);
  }

  async function handleSaveEdit(data: StrategyFormData) {
    if (!editing) return;
    const updated = await api.updateStrategy(editing.id, data);
    setStrategies((prev) => prev.map((s) => (s.id === updated.id ? updated : s)));
    setEditing(null);
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
                onSave={handleSaveEdit}
                onCancel={handleCancel}
                isEditing
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
            onSave={handleSaveNew}
            onCancel={handleCancel}
            cloneTemplates={cloneTemplates}
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
// Helper: Map probe strategy to form data
// =============================================================================

function mapProbeToFormData(s: ThemeStrategyDetail): Partial<StrategyDefinition> {
  const details = s.details || {};
  return {
    name: s.name,
    display_name: s.display_name,
    description: s.philosophy,
    category: (s.direction === 'long' || s.direction === 'short' ? 'custom' : 'custom') as StrategyCategory,
    direction: s.direction === 'long_short' ? 'long_short'
      : s.direction === 'long_only' ? 'long_only'
      : s.direction === 'short_only' ? 'short_only'
      : 'long_short',
    entry_long: typeof details.entry_long === 'string' ? details.entry_long : null,
    entry_short: typeof details.entry_short === 'string' ? details.entry_short : null,
    exit_long: typeof details.exit === 'string' ? details.exit : null,
    required_features: Array.isArray(details.indicators) ? details.indicators : null,
    tags: Array.isArray(details.tags) ? details.tags : null,
  };
}

// =============================================================================
// Helpers
// =============================================================================

/** Render condition text — structured DSL gets human-readable summary, plain text passes through. */
function renderConditionText(value: string, joiner: 'AND' | 'OR'): string {
  const nodes = parseConditions(value);
  if (nodes) return conditionsToText(nodes, joiner);
  return value;
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
            <h3 className="text-sm font-medium">{strategy.display_name || strategy.name}</h3>
            <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${
              strategy.is_active
                ? 'bg-[var(--accent-green)]/10 text-[var(--accent-green)]'
                : 'bg-[var(--bg-primary)] text-[var(--text-secondary)]'
            }`}>
              {strategy.is_active ? 'Active' : 'Inactive'}
            </span>
            <span className="rounded bg-[var(--accent-blue)]/10 px-1.5 py-0.5 text-[10px] font-medium text-[var(--accent-blue)]">
              {CATEGORY_LABELS[strategy.category] || strategy.category}
            </span>
            <span className="rounded bg-[var(--bg-primary)] px-1.5 py-0.5 text-[10px] text-[var(--text-secondary)]">
              {DIRECTION_LABELS[strategy.direction] || strategy.direction}
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
          <span>{strategy.timeframes.length > 0 ? strategy.timeframes.join(', ') : 'None'}</span>
        </div>
        <div>
          <span className="text-[var(--text-secondary)]">Max Risk: </span>
          <span className="font-mono">{strategy.max_risk_pct}%</span>
          <span className="text-[var(--text-secondary)]"> / Min R:R: </span>
          <span className="font-mono">{strategy.min_risk_reward}</span>
        </div>
      </div>

      {(strategy.entry_long || strategy.exit_long) && (
        <div className="mt-2 grid grid-cols-2 gap-3 text-xs">
          {strategy.entry_long && (
            <div>
              <span className="text-[var(--text-secondary)]">Entry: </span>
              <span>{renderConditionText(strategy.entry_long, 'AND')}</span>
            </div>
          )}
          {strategy.exit_long && (
            <div>
              <span className="text-[var(--text-secondary)]">Exit: </span>
              <span>{renderConditionText(strategy.exit_long, 'OR')}</span>
            </div>
          )}
        </div>
      )}

      {strategy.tags && strategy.tags.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {strategy.tags.map((tag) => (
            <span key={tag} className="rounded-full bg-[var(--bg-primary)] px-2 py-0.5 text-[10px] text-[var(--text-secondary)]">
              {tag}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
