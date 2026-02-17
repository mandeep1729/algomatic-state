/**
 * Modal for editing the decision context of a trade fill.
 *
 * Fetches the fill's context on open and allows the user to edit:
 * - Strategy (via dropdown)
 * - Hypothesis
 * - Exit intent
 * - Emotions/feelings at decision time
 * - Notes
 *
 * Saves the context when the user clicks Save.
 */

import { useCallback, useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { Modal } from './Modal';
import { StrategyChips } from './campaigns/StrategyChips';
import { EmotionChips } from './campaigns/EmotionChips';
import { fetchFillContext, saveFillContext } from '../api';
import { fetchStrategies } from '../api/client';
import type { FillContextDetail, StrategyDefinition } from '../types';

interface FillContextModalProps {
  /** Whether the modal is open */
  isOpen: boolean;
  /** Callback to close the modal */
  onClose: () => void;
  /** The fill ID to load/save context for */
  fillId: string;
  /** Symbol for display in title */
  symbol: string;
  /** Callback when context is saved successfully */
  onSave?: () => void;
}

const EXIT_INTENT_OPTIONS: { value: string; label: string }[] = [
  { value: 'unknown', label: 'Unknown' },
  { value: 'fixed', label: 'Fixed target' },
  { value: 'trail', label: 'Trailing' },
  { value: 'scale', label: 'Scale out' },
  { value: 'time', label: 'Time-based' },
];

interface Draft {
  strategyTags: string[];
  strategyId: number | null;
  hypothesis: string;
  exitIntent: string;
  feelingsThenChips: string[];
  feelingsThenIntensity: number;
  notes: string;
}

export function FillContextModal({
  isOpen,
  onClose,
  fillId,
  symbol,
  onSave,
}: FillContextModalProps) {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [context, setContext] = useState<FillContextDetail | null>(null);
  const [strategies, setStrategies] = useState<StrategyDefinition[]>([]);

  const [draft, setDraft] = useState<Draft>({
    strategyTags: [],
    strategyId: null,
    hypothesis: '',
    exitIntent: 'unknown',
    feelingsThenChips: [],
    feelingsThenIntensity: 2,
    notes: '',
  });

  // Load context and strategies when modal opens
  useEffect(() => {
    if (!isOpen) return;

    let cancelled = false;
    setLoading(true);
    setError(null);

    async function load() {
      try {
        const [contextData, strategiesData] = await Promise.all([
          fetchFillContext(fillId),
          fetchStrategies(),
        ]);

        if (cancelled) return;

        setContext(contextData);
        setStrategies(strategiesData);

        // Initialize draft from context
        // Note: strategyTags uses strategy IDs (strings) to match StrategyChips component
        setDraft({
          strategyTags: contextData.strategy_id ? [String(contextData.strategy_id)] : [],
          strategyId: contextData.strategy_id,
          hypothesis: contextData.hypothesis || '',
          exitIntent: contextData.exit_intent || 'unknown',
          feelingsThenChips: contextData.feelings_then?.chips || [],
          feelingsThenIntensity: contextData.feelings_then?.intensity ?? 2,
          notes: contextData.notes || '',
        });
      } catch (err) {
        if (!cancelled) {
          console.error('[FillContextModal] Failed to load context:', err);
          setError(err instanceof Error ? err.message : 'Failed to load context');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => { cancelled = true; };
  }, [isOpen, fillId]);

  const updateDraft = <K extends keyof Draft>(key: K, value: Draft[K]) => {
    setDraft((prev) => ({ ...prev, [key]: value }));
  };

  // Handle strategy selection change
  // Note: tags array contains strategy IDs (strings), not names
  const handleStrategyChange = (tags: string[]) => {
    updateDraft('strategyTags', tags);
    // Convert string ID to number for the API
    if (tags.length > 0) {
      updateDraft('strategyId', parseInt(tags[0], 10));
    } else {
      updateDraft('strategyId', null);
    }
  };

  const handleSave = useCallback(async () => {
    if (!context) return;

    setSaving(true);
    setError(null);

    try {
      await saveFillContext(fillId, {
        strategy_id: draft.strategyId,
        hypothesis: draft.hypothesis.trim() || null,
        exit_intent: draft.exitIntent,
        feelings_then: {
          chips: draft.feelingsThenChips,
          intensity: draft.feelingsThenIntensity,
        },
        notes: draft.notes.trim() || null,
      });

      onSave?.();
      onClose();
    } catch (err) {
      console.error('[FillContextModal] Failed to save context:', err);
      setError(err instanceof Error ? err.message : 'Failed to save context');
    } finally {
      setSaving(false);
    }
  }, [context, fillId, draft, onSave, onClose]);

  const canSave = context != null;

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={`Edit Context - ${symbol}`}
      maxWidth="max-w-xl"
    >
      <div className="p-4">
        {loading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-[var(--accent-blue)]" />
            <span className="ml-2 text-sm text-[var(--text-secondary)]">Loading...</span>
          </div>
        ) : error && !context ? (
          <div className="rounded-md bg-red-500/10 p-4 text-sm text-red-500">
            {error}
          </div>
        ) : (
          <div className="space-y-5">
            {/* Strategy tags */}
            <div>
              <label className="mb-1.5 block text-xs font-medium text-[var(--text-secondary)]">
                Strategy tags
              </label>
              <StrategyChips
                value={draft.strategyTags}
                onChange={handleStrategyChange}
                strategies={strategies}
                loading={false}
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
                onChange={(e) => updateDraft('exitIntent', e.target.value)}
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

            {/* Error message */}
            {error && (
              <div className="rounded-md bg-red-500/10 p-3 text-sm text-red-500">
                {error}
              </div>
            )}

            {/* Actions */}
            <div className="flex justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={onClose}
                className="rounded-md border border-[var(--border-color)] px-4 py-2 text-sm text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-primary)] transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleSave}
                disabled={saving || !canSave}
                className="inline-flex items-center gap-2 rounded-md bg-[var(--accent-blue)] px-4 py-2 text-sm font-medium text-white hover:bg-[var(--accent-blue)]/90 disabled:cursor-not-allowed disabled:opacity-50 transition-colors"
              >
                {saving && <Loader2 className="h-4 w-4 animate-spin" />}
                Save
              </button>
            </div>
          </div>
        )}
      </div>
    </Modal>
  );
}
