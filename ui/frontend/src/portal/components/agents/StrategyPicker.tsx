import { useEffect, useState } from 'react';
import { Plus } from 'lucide-react';
import { createAgentStrategy, fetchAllProbeStrategies } from '../../api';
import type { AgentStrategy, StrategyCategory, StrategyDirection } from '../../types';
import type { ThemeStrategyDetail } from '../../api';
import { StrategyForm, type CloneTemplate, type StrategyFormData } from '../strategies/StrategyForm';

interface StrategyPickerProps {
  strategies: AgentStrategy[];
  selectedId: number | null;
  onSelect: (id: number) => void;
  onStrategyCreated: (strategy: AgentStrategy) => void;
}

export function StrategyPicker({ strategies, selectedId, onSelect, onStrategyCreated }: StrategyPickerProps) {
  const [creatingNew, setCreatingNew] = useState(false);
  const [cloneTemplates, setCloneTemplates] = useState<CloneTemplate[]>([]);

  // Load clone templates when creating
  useEffect(() => {
    if (!creatingNew) return;
    let cancelled = false;

    async function loadTemplates() {
      const templates: CloneTemplate[] = [];

      // Agent strategies already passed in as props — use those
      for (const s of strategies) {
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
  }, [creatingNew, strategies]);

  async function handleCreateStrategy(data: StrategyFormData) {
    const created = await createAgentStrategy({
      name: data.name,
      display_name: data.display_name,
      description: data.description || null,
      category: data.category,
      direction: data.direction,
      entry_long: data.entry_long,
      entry_short: data.entry_short,
      exit_long: data.exit_long,
      required_features: data.required_features,
      tags: data.tags,
      timeframes: data.timeframes,
      max_risk_pct: data.max_risk_pct,
      min_risk_reward: data.min_risk_reward,
      atr_stop_mult: data.atr_stop_mult,
      atr_target_mult: data.atr_target_mult,
      trailing_atr_mult: data.trailing_atr_mult,
      time_stop_bars: data.time_stop_bars,
    } as Partial<AgentStrategy>);
    onStrategyCreated(created);
    onSelect(created.id);
    setCreatingNew(false);
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
        <StrategyForm
          onSave={handleCreateStrategy}
          onCancel={() => setCreatingNew(false)}
          cloneTemplates={cloneTemplates}
        />
      )}
    </div>
  );
}

// =============================================================================
// Helper: Map probe strategy to form data
// =============================================================================

function mapProbeToFormData(s: ThemeStrategyDetail): Partial<import('../../types').StrategyDefinition> {
  const details = s.details || {};
  return {
    name: s.name,
    display_name: s.display_name,
    description: s.philosophy,
    direction: s.direction === 'long_short' ? 'long_short'
      : s.direction === 'long_only' ? 'long_only'
      : s.direction === 'short_only' ? 'short_only'
      : 'long_short',
    entry_long: typeof details.entry_long === 'string' ? details.entry_long : null,
    entry_short: typeof details.entry_short === 'string' ? details.entry_short : null,
    exit_long: typeof details.exit === 'string' ? details.exit : null,
    required_features: Array.isArray(details.indicators) ? details.indicators as string[] : null,
    tags: Array.isArray(details.tags) ? details.tags as string[] : null,
  };
}
