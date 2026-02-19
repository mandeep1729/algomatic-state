import { useCallback, useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { Modal } from '../Modal';
import { StrategyPicker } from './StrategyPicker';
import { fetchAgentStrategies, cloneAgentStrategy, createAgent, updateAgent } from '../../api';
import type { AgentStrategy, AgentSummary, AgentCreateRequest, AgentUpdateRequest } from '../../types';
import { createLogger } from '../../utils/logger';

const log = createLogger('CreateAgentModal');

type Step = 'basic' | 'strategy' | 'config';

const TIMEFRAME_OPTIONS = [
  { value: '1Min', label: '1 Minute' },
  { value: '5Min', label: '5 Minutes' },
  { value: '15Min', label: '15 Minutes' },
  { value: '1Hour', label: '1 Hour' },
  { value: '1Day', label: '1 Day' },
];

interface CreateAgentModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCreated: (agent: AgentSummary) => void;
  editAgent?: AgentSummary;
}

export function CreateAgentModal({ isOpen, onClose, onCreated, editAgent }: CreateAgentModalProps) {
  const isEdit = !!editAgent;

  // Step state
  const [step, setStep] = useState<Step>('basic');

  // Form fields
  const [name, setName] = useState('');
  const [symbol, setSymbol] = useState('');
  const [strategyId, setStrategyId] = useState<number | null>(null);
  const [timeframe, setTimeframe] = useState('5Min');
  const [positionSize, setPositionSize] = useState(1000);
  const [intervalMinutes, setIntervalMinutes] = useState(5);
  const [lookbackDays, setLookbackDays] = useState(30);
  const [paper, setPaper] = useState(true);

  // Strategy data
  const [strategies, setStrategies] = useState<AgentStrategy[]>([]);
  const [strategiesLoading, setStrategiesLoading] = useState(false);

  // Submission state
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Pre-fill form for edit mode
  useEffect(() => {
    if (isOpen && editAgent) {
      setName(editAgent.name);
      setSymbol(editAgent.symbol);
      setStrategyId(editAgent.strategy_id);
      setTimeframe(editAgent.timeframe);
      setPositionSize(editAgent.position_size_dollars);
      setIntervalMinutes(editAgent.interval_minutes);
      setLookbackDays(editAgent.lookback_days);
      setPaper(editAgent.paper);
      setStep('basic');
    } else if (isOpen) {
      setName('');
      setSymbol('');
      setStrategyId(null);
      setTimeframe('5Min');
      setPositionSize(1000);
      setIntervalMinutes(5);
      setLookbackDays(30);
      setPaper(true);
      setStep('basic');
    }
    setError(null);
  }, [isOpen, editAgent]);

  // Lazy-load strategies when modal opens
  useEffect(() => {
    if (!isOpen) return;
    let cancelled = false;

    async function load() {
      setStrategiesLoading(true);
      try {
        const data = await fetchAgentStrategies();
        if (!cancelled) setStrategies(data);
      } catch (err) {
        log.error('Failed to load strategies', err);
      } finally {
        if (!cancelled) setStrategiesLoading(false);
      }
    }

    load();
    return () => { cancelled = true; };
  }, [isOpen]);

  const handleClone = useCallback(async (srcId: number) => {
    const src = strategies.find((s) => s.id === srcId);
    if (!src) return;
    try {
      const cloned = await cloneAgentStrategy(srcId, `${src.display_name} (Custom)`);
      setStrategies((prev) => [...prev, cloned]);
      setStrategyId(cloned.id);
    } catch (err) {
      log.error('Failed to clone strategy', err);
      setError(err instanceof Error ? err.message : 'Failed to clone strategy');
    }
  }, [strategies]);

  const handleSubmit = useCallback(async () => {
    setError(null);
    setSubmitting(true);

    try {
      if (isEdit && editAgent) {
        const updates: AgentUpdateRequest = {
          name: name.trim(),
          symbol: symbol.trim().toUpperCase(),
          strategy_id: strategyId ?? undefined,
          timeframe,
          interval_minutes: intervalMinutes,
          lookback_days: lookbackDays,
          position_size_dollars: positionSize,
          paper,
        };
        const updated = await updateAgent(editAgent.id, updates);
        onCreated(updated);
      } else {
        if (!strategyId) {
          setError('Please select a strategy');
          setSubmitting(false);
          return;
        }
        const data: AgentCreateRequest = {
          name: name.trim(),
          symbol: symbol.trim().toUpperCase(),
          strategy_id: strategyId,
          timeframe,
          interval_minutes: intervalMinutes,
          lookback_days: lookbackDays,
          position_size_dollars: positionSize,
          paper,
        };
        const created = await createAgent(data);
        onCreated(created);
      }
      onClose();
    } catch (err) {
      log.error('Failed to save agent', err);
      setError(err instanceof Error ? err.message : 'Failed to save agent');
    } finally {
      setSubmitting(false);
    }
  }, [isEdit, editAgent, name, symbol, strategyId, timeframe, positionSize, intervalMinutes, lookbackDays, paper, onCreated, onClose]);

  const canGoToStrategy = name.trim().length > 0 && symbol.trim().length > 0;
  const canGoToConfig = strategyId !== null;

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={isEdit ? 'Edit Agent' : 'New Agent'} maxWidth="max-w-2xl">
      <div className="p-4">
        {/* Step indicators */}
        <div className="mb-5 flex items-center gap-2 text-xs">
          {(['basic', 'strategy', 'config'] as const).map((s, i) => {
            const labels = ['Basic Info', 'Strategy', 'Configuration'];
            const isCurrent = step === s;
            const isPast = (['basic', 'strategy', 'config'] as const).indexOf(step) > i;
            return (
              <div key={s} className="flex items-center gap-2">
                {i > 0 && <div className="h-px w-6 bg-[var(--border-color)]" />}
                <span
                  className={`inline-flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold ${
                    isCurrent
                      ? 'bg-[var(--accent-blue)] text-white'
                      : isPast
                        ? 'bg-[var(--accent-green)]/20 text-[var(--accent-green)]'
                        : 'bg-[var(--bg-tertiary)] text-[var(--text-secondary)]'
                  }`}
                >
                  {i + 1}
                </span>
                <span className={`${isCurrent ? 'text-[var(--text-primary)] font-medium' : 'text-[var(--text-secondary)]'}`}>
                  {labels[i]}
                </span>
              </div>
            );
          })}
        </div>

        {/* Step 1: Basic Info */}
        {step === 'basic' && (
          <div className="space-y-4">
            <div>
              <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">Agent Name</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g., AAPL Trend Bot"
                className="form-input h-9 w-full text-sm"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">Symbol</label>
              <input
                type="text"
                value={symbol}
                onChange={(e) => setSymbol(e.target.value.toUpperCase())}
                placeholder="e.g., AAPL"
                className="form-input h-9 w-full text-sm"
              />
            </div>
            <div className="flex justify-end">
              <button
                type="button"
                onClick={() => setStep('strategy')}
                disabled={!canGoToStrategy}
                className="inline-flex h-9 items-center rounded-md bg-[var(--accent-blue)] px-4 text-xs font-medium text-white transition-colors hover:bg-[var(--accent-blue)]/90 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Next
              </button>
            </div>
          </div>
        )}

        {/* Step 2: Strategy */}
        {step === 'strategy' && (
          <div className="space-y-4">
            {strategiesLoading ? (
              <div className="flex items-center justify-center py-8 text-sm text-[var(--text-secondary)]">
                <Loader2 size={16} className="mr-2 animate-spin" />
                Loading strategies...
              </div>
            ) : (
              <StrategyPicker
                strategies={strategies}
                selectedId={strategyId}
                onSelect={setStrategyId}
                onClone={handleClone}
              />
            )}
            <div className="flex justify-between">
              <button
                type="button"
                onClick={() => setStep('basic')}
                className="inline-flex h-9 items-center rounded-md border border-[var(--border-color)] px-4 text-xs text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-primary)]"
              >
                Back
              </button>
              <button
                type="button"
                onClick={() => setStep('config')}
                disabled={!canGoToConfig}
                className="inline-flex h-9 items-center rounded-md bg-[var(--accent-blue)] px-4 text-xs font-medium text-white transition-colors hover:bg-[var(--accent-blue)]/90 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Next
              </button>
            </div>
          </div>
        )}

        {/* Step 3: Configuration */}
        {step === 'config' && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">Timeframe</label>
                <select
                  value={timeframe}
                  onChange={(e) => setTimeframe(e.target.value)}
                  className="form-input h-9 w-full text-sm"
                >
                  {TIMEFRAME_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">Position Size ($)</label>
                <input
                  type="number"
                  value={positionSize}
                  onChange={(e) => setPositionSize(Number(e.target.value))}
                  min={1}
                  className="form-input h-9 w-full text-sm"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">Interval (minutes)</label>
                <input
                  type="number"
                  value={intervalMinutes}
                  onChange={(e) => setIntervalMinutes(Number(e.target.value))}
                  min={1}
                  className="form-input h-9 w-full text-sm"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">Lookback (days)</label>
                <input
                  type="number"
                  value={lookbackDays}
                  onChange={(e) => setLookbackDays(Number(e.target.value))}
                  min={1}
                  className="form-input h-9 w-full text-sm"
                />
              </div>
            </div>

            {/* Paper toggle */}
            <label className="flex items-center gap-3 cursor-pointer">
              <div
                role="switch"
                aria-checked={paper}
                onClick={() => setPaper(!paper)}
                className={`relative h-5 w-9 rounded-full transition-colors ${paper ? 'bg-[var(--accent-blue)]' : 'bg-[var(--bg-tertiary)]'}`}
              >
                <div className={`absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform ${paper ? 'translate-x-4' : 'translate-x-0.5'}`} />
              </div>
              <span className="text-sm text-[var(--text-primary)]">Paper Trading</span>
              <span className="text-xs text-[var(--text-secondary)]">{paper ? 'Simulated orders' : 'Live orders'}</span>
            </label>

            {/* Error */}
            {error && (
              <p className="text-xs text-[var(--accent-red)]">{error}</p>
            )}

            <div className="flex justify-between">
              <button
                type="button"
                onClick={() => setStep('strategy')}
                className="inline-flex h-9 items-center rounded-md border border-[var(--border-color)] px-4 text-xs text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-primary)]"
              >
                Back
              </button>
              <button
                type="button"
                onClick={handleSubmit}
                disabled={submitting}
                className="inline-flex h-9 items-center gap-1.5 rounded-md bg-[var(--accent-blue)] px-5 text-xs font-medium text-white transition-colors hover:bg-[var(--accent-blue)]/90 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {submitting && <Loader2 size={14} className="animate-spin" />}
                {isEdit ? 'Save Changes' : 'Create Agent'}
              </button>
            </div>
          </div>
        )}
      </div>
    </Modal>
  );
}
