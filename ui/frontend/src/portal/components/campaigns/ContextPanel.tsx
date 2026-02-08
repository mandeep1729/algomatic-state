import { useEffect, useMemo, useRef, useState } from 'react';
import type { DecisionContext, StrategyDefinition } from '../../types';
import api from '../../api';
import { StrategyChips } from './StrategyChips';
import { EmotionChips } from './EmotionChips';

interface Draft {
  strategyTags: string[];
  hypothesis: string;
  exitIntent: DecisionContext['exitIntent'];
  feelingsThenChips: string[];
  feelingsThenIntensity: number;
  notes: string;
}

interface ContextPanelProps {
  title: string;
  initial?: DecisionContext;
  onAutosave: (ctx: DecisionContext) => void;
  scope: DecisionContext['scope'];
  contextType: DecisionContext['contextType'];
  campaignId?: string;
  legId?: string;
}

const EXIT_INTENT_OPTIONS: { value: NonNullable<DecisionContext['exitIntent']>; label: string }[] = [
  { value: 'unknown', label: 'Unknown' },
  { value: 'fixed', label: 'Fixed target' },
  { value: 'trail', label: 'Trailing' },
  { value: 'scale', label: 'Scale out' },
  { value: 'time', label: 'Time-based' },
];

export function ContextPanel({
  title,
  initial,
  onAutosave,
  scope,
  contextType,
  campaignId,
  legId,
}: ContextPanelProps) {
  const initialDraft: Draft = useMemo(
    () => ({
      strategyTags: initial?.strategyTags ?? [],
      hypothesis: initial?.hypothesis ?? '',
      exitIntent: initial?.exitIntent ?? 'unknown',
      feelingsThenChips: initial?.feelingsThen?.chips ?? [],
      feelingsThenIntensity: initial?.feelingsThen?.intensity ?? 2,
      notes: initial?.notes ?? '',
    }),
    [initial],
  );

  const [draft, setDraft] = useState<Draft>(initialDraft);
  // Track whether the user has edited anything (skip autosave on mount / tab switch)
  const dirtyRef = useRef(false);

  // Strategies fetched from API
  const [strategies, setStrategies] = useState<StrategyDefinition[]>([]);
  const [strategiesLoading, setStrategiesLoading] = useState(true);

  // Fetch strategies on mount
  useEffect(() => {
    let cancelled = false;
    async function loadStrategies() {
      setStrategiesLoading(true);
      try {
        const data = await api.fetchStrategies();
        if (!cancelled) {
          setStrategies(data);
        }
      } catch (err) {
        console.error('[ContextPanel] Failed to fetch strategies:', err);
        if (!cancelled) {
          setStrategies([]);
        }
      } finally {
        if (!cancelled) {
          setStrategiesLoading(false);
        }
      }
    }
    loadStrategies();
    return () => { cancelled = true; };
  }, []);

  // Sync when initial prop changes (e.g. switching legs)
  useEffect(() => {
    setDraft(initialDraft);
    dirtyRef.current = false;
  }, [initialDraft]);

  // Debounced autosave — only fires after user edits, 5s debounce
  useEffect(() => {
    if (!dirtyRef.current) return;

    const timer = setTimeout(() => {
      const next: DecisionContext = {
        contextId: initial?.contextId ?? crypto.randomUUID(),
        scope,
        contextType,
        campaignId,
        legId,
        strategyTags: draft.strategyTags,
        hypothesis: draft.hypothesis.trim() || undefined,
        exitIntent: draft.exitIntent,
        feelingsThen: {
          chips: draft.feelingsThenChips,
          intensity: draft.feelingsThenIntensity,
        },
        notes: draft.notes.trim() || undefined,
        updatedAt: new Date().toISOString(),
      };
      onAutosave(next);
    }, 5000);

    return () => clearTimeout(timer);
  }, [draft, initial?.contextId, scope, contextType, campaignId, legId, onAutosave]);

  const updateDraft = <K extends keyof Draft>(key: K, value: Draft[K]) => {
    dirtyRef.current = true;
    setDraft((prev) => ({ ...prev, [key]: value }));
  };

  return (
    <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)]">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[var(--border-color)] px-4 py-3">
        <h3 className="text-sm font-medium text-[var(--text-primary)]">{title}</h3>
        <span className="text-xs text-[var(--text-secondary)]">Autosaves</span>
      </div>

      {/* Body */}
      <div className="space-y-5 p-4">
        {/* Strategy tags */}
        <div>
          <label className="mb-1.5 block text-xs font-medium text-[var(--text-secondary)]">
            Strategy tags
          </label>
          <StrategyChips
            value={draft.strategyTags}
            onChange={(v) => updateDraft('strategyTags', v)}
            strategies={strategies}
            loading={strategiesLoading}
          />
        </div>

        {/* Hypothesis */}
        <div>
          <label className="mb-1.5 block text-xs font-medium text-[var(--text-secondary)]">
            Hypothesis (what must be true)
          </label>
          <textarea
            value={draft.hypothesis}
            onChange={(e) => updateDraft('hypothesis', e.target.value)}
            placeholder="One or two sentences is enough..."
            rows={2}
            className="w-full rounded-md border border-[var(--border-color)] bg-[var(--bg-primary)] px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-secondary)] focus:border-[var(--accent-blue)] focus:outline-none"
          />
        </div>

        {/* Exit intent */}
        <div>
          <label className="mb-1.5 block text-xs font-medium text-[var(--text-secondary)]">
            Exit intent
          </label>
          <select
            value={draft.exitIntent}
            onChange={(e) =>
              updateDraft('exitIntent', e.target.value as DecisionContext['exitIntent'])
            }
            className="w-full rounded-md border border-[var(--border-color)] bg-[var(--bg-primary)] px-3 py-2 text-sm text-[var(--text-primary)] focus:border-[var(--accent-blue)] focus:outline-none"
          >
            {EXIT_INTENT_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        {/* Feelings at decision */}
        <div>
          <label className="mb-1.5 block text-xs font-medium text-[var(--text-secondary)]">
            Feelings at decision
          </label>
          <EmotionChips
            value={draft.feelingsThenChips}
            onChange={(v) => updateDraft('feelingsThenChips', v)}
          />
          <div className="mt-2 flex items-center gap-3">
            <span className="text-xs text-[var(--text-secondary)]">Intensity</span>
            <input
              type="range"
              min={0}
              max={5}
              value={draft.feelingsThenIntensity}
              onChange={(e) => updateDraft('feelingsThenIntensity', Number(e.target.value))}
              className="h-1.5 flex-1 cursor-pointer appearance-none rounded-full bg-[var(--bg-tertiary)] accent-[var(--accent-blue)]"
            />
            <span className="w-4 text-center text-xs font-medium text-[var(--text-primary)]">
              {draft.feelingsThenIntensity}
            </span>
          </div>
        </div>

        {/* Notes */}
        <div>
          <label className="mb-1.5 block text-xs font-medium text-[var(--text-secondary)]">
            Notes (optional)
          </label>
          <textarea
            value={draft.notes}
            onChange={(e) => updateDraft('notes', e.target.value)}
            placeholder="Anything else worth noting..."
            rows={3}
            className="w-full rounded-md border border-[var(--border-color)] bg-[var(--bg-primary)] px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-secondary)] focus:border-[var(--accent-blue)] focus:outline-none"
          />
        </div>
      </div>
    </div>
  );
}
