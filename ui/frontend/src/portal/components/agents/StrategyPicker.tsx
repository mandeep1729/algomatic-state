import { useEffect, useMemo, useState } from 'react';
import { Plus } from 'lucide-react';
import { createAgentStrategy, fetchAllProbeStrategies } from '../../api';
import type { AgentStrategy, StrategyCategory, StrategyDirection } from '../../types';
import { StrategyForm, type CloneTemplate, type StrategyFormData } from '../strategies/StrategyForm';
import { mapProbeToFormData } from '../strategies/mapProbeToFormData';
import { parseConditions, conditionsToText } from '../strategies/conditionUtils';

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

  const selectedStrategy = useMemo(
    () => strategies.find((s) => s.id === selectedId) ?? null,
    [strategies, selectedId],
  );

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

      {/* Selected strategy details */}
      {selectedStrategy && !creatingNew && (
        <StrategyDetails strategy={selectedStrategy} />
      )}

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

// ---------------------------------------------------------------------------
// Strategy Details (read-only summary of selected strategy)
// ---------------------------------------------------------------------------

/** Render condition text -- structured DSL gets human-readable summary, plain text passes through. */
function renderConditionText(value: string, joiner: 'AND' | 'OR'): string {
  const nodes = parseConditions(value);
  if (nodes) return conditionsToText(nodes, joiner);
  return value;
}

function StrategyDetails({ strategy }: { strategy: AgentStrategy }) {
  const hasEntryExit = strategy.entry_long || strategy.entry_short || strategy.exit_long || strategy.exit_short;
  const hasAtrParams =
    strategy.atr_stop_mult != null ||
    strategy.atr_target_mult != null ||
    strategy.trailing_atr_mult != null ||
    strategy.time_stop_bars != null;

  return (
    <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-3 space-y-2.5">
      {/* Header row: category + direction badges */}
      <div className="flex items-center gap-2">
        <span className="rounded bg-[var(--accent-blue)]/10 px-1.5 py-0.5 text-[10px] font-medium text-[var(--accent-blue)]">
          {CATEGORY_LABELS[strategy.category] || strategy.category}
        </span>
        <span className="rounded bg-[var(--bg-primary)] px-1.5 py-0.5 text-[10px] text-[var(--text-secondary)]">
          {DIRECTION_LABELS[strategy.direction] || strategy.direction}
        </span>
        {strategy.is_predefined && (
          <span className="rounded bg-[var(--bg-primary)] px-1.5 py-0.5 text-[10px] text-[var(--text-secondary)]">
            Predefined
          </span>
        )}
      </div>

      {/* Description */}
      {strategy.description && (
        <p className="text-xs text-[var(--text-secondary)]">{strategy.description}</p>
      )}

      {/* Timeframes + Risk */}
      <div className="grid grid-cols-2 gap-3 text-xs">
        <div>
          <span className="text-[var(--text-secondary)]">Timeframes: </span>
          <span>{strategy.timeframes && strategy.timeframes.length > 0 ? strategy.timeframes.join(', ') : 'None'}</span>
        </div>
        <div>
          <span className="text-[var(--text-secondary)]">Max Risk: </span>
          <span className="font-mono">{strategy.max_risk_pct ?? '-'}%</span>
          <span className="text-[var(--text-secondary)]"> / Min R:R: </span>
          <span className="font-mono">{strategy.min_risk_reward ?? '-'}</span>
        </div>
      </div>

      {/* Entry / Exit conditions */}
      {hasEntryExit && (
        <div className="grid grid-cols-2 gap-3 text-xs">
          {strategy.entry_long && (
            <div>
              <span className="text-[var(--text-secondary)]">Entry Long: </span>
              <span>{renderConditionText(strategy.entry_long, 'AND')}</span>
            </div>
          )}
          {strategy.entry_short && (
            <div>
              <span className="text-[var(--text-secondary)]">Entry Short: </span>
              <span>{renderConditionText(strategy.entry_short, 'AND')}</span>
            </div>
          )}
          {strategy.exit_long && (
            <div>
              <span className="text-[var(--text-secondary)]">Exit Long: </span>
              <span>{renderConditionText(strategy.exit_long, 'OR')}</span>
            </div>
          )}
          {strategy.exit_short && (
            <div>
              <span className="text-[var(--text-secondary)]">Exit Short: </span>
              <span>{renderConditionText(strategy.exit_short, 'OR')}</span>
            </div>
          )}
        </div>
      )}

      {/* ATR parameters */}
      {hasAtrParams && (
        <div className="grid grid-cols-2 gap-3 text-xs">
          {strategy.atr_stop_mult != null && (
            <div>
              <span className="text-[var(--text-secondary)]">ATR Stop: </span>
              <span className="font-mono">{strategy.atr_stop_mult}x</span>
            </div>
          )}
          {strategy.atr_target_mult != null && (
            <div>
              <span className="text-[var(--text-secondary)]">ATR Target: </span>
              <span className="font-mono">{strategy.atr_target_mult}x</span>
            </div>
          )}
          {strategy.trailing_atr_mult != null && (
            <div>
              <span className="text-[var(--text-secondary)]">Trailing ATR: </span>
              <span className="font-mono">{strategy.trailing_atr_mult}x</span>
            </div>
          )}
          {strategy.time_stop_bars != null && (
            <div>
              <span className="text-[var(--text-secondary)]">Time Stop: </span>
              <span className="font-mono">{strategy.time_stop_bars} bars</span>
            </div>
          )}
        </div>
      )}

      {/* Tags */}
      {strategy.tags && strategy.tags.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {strategy.tags.map((tag) => (
            <span key={tag} className="rounded-full bg-[var(--bg-primary)] px-2 py-0.5 text-[10px] text-[var(--text-secondary)]">
              {tag}
            </span>
          ))}
        </div>
      )}

      {/* Indicators */}
      {strategy.required_features && strategy.required_features.length > 0 && (
        <div className="text-xs">
          <span className="text-[var(--text-secondary)]">Indicators: </span>
          <span>{strategy.required_features.join(', ')}</span>
        </div>
      )}
    </div>
  );
}
