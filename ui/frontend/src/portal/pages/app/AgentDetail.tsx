import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { Pencil, Trash2, Play, Pause, Square, AlertTriangle, Loader2 } from 'lucide-react';
import { fetchAgent, startAgent, pauseAgent, stopAgent, deleteAgent, fetchAgentOrders, fetchAgentActivity } from '../../api';
import { AgentStatusBadge } from '../../components/agents/AgentStatusBadge';
import { AgentOrdersTable } from '../../components/agents/AgentOrdersTable';
import { AgentActivityLog } from '../../components/agents/AgentActivityLog';
import { CreateAgentModal } from '../../components/agents/CreateAgentModal';
import { Modal } from '../../components/Modal';
import type { AgentSummary, AgentStatus, AgentOrder, AgentActivity } from '../../types';
import { createLogger } from '../../utils/logger';

const log = createLogger('AgentDetail');

type TabKey = 'orders' | 'activity';

export default function AgentDetail() {
  const { agentId } = useParams<{ agentId: string }>();
  const navigate = useNavigate();

  const [agent, setAgent] = useState<AgentSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);

  const [tab, setTab] = useState<TabKey>('orders');
  const [orders, setOrders] = useState<AgentOrder[]>([]);
  const [activities, setActivities] = useState<AgentActivity[]>([]);
  const [ordersLoading, setOrdersLoading] = useState(false);
  const [activitiesLoading, setActivitiesLoading] = useState(false);

  const [showEditModal, setShowEditModal] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  // Load agent
  useEffect(() => {
    if (!agentId) return;
    let cancelled = false;

    async function load() {
      setLoading(true);
      try {
        const data = await fetchAgent(Number(agentId));
        if (!cancelled) setAgent(data);
      } catch (err) {
        log.error('Failed to load agent', err);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => { cancelled = true; };
  }, [agentId]);

  // Load orders when tab is orders
  useEffect(() => {
    if (!agentId || tab !== 'orders') return;
    let cancelled = false;

    async function load() {
      setOrdersLoading(true);
      try {
        const data = await fetchAgentOrders(Number(agentId));
        if (!cancelled) setOrders(data);
      } catch (err) {
        log.error('Failed to load orders', err);
      } finally {
        if (!cancelled) setOrdersLoading(false);
      }
    }

    load();
    return () => { cancelled = true; };
  }, [agentId, tab]);

  // Load activity when tab is activity
  useEffect(() => {
    if (!agentId || tab !== 'activity') return;
    let cancelled = false;

    async function load() {
      setActivitiesLoading(true);
      try {
        const data = await fetchAgentActivity(Number(agentId));
        if (!cancelled) setActivities(data);
      } catch (err) {
        log.error('Failed to load activities', err);
      } finally {
        if (!cancelled) setActivitiesLoading(false);
      }
    }

    load();
    return () => { cancelled = true; };
  }, [agentId, tab]);

  // Lifecycle actions
  const handleLifecycleAction = useCallback(async (action: 'start' | 'pause' | 'stop') => {
    if (!agent) return;
    setActionLoading(true);
    try {
      let updated: AgentSummary;
      if (action === 'start') updated = await startAgent(agent.id);
      else if (action === 'pause') updated = await pauseAgent(agent.id);
      else updated = await stopAgent(agent.id);
      setAgent(updated);
    } catch (err) {
      log.error(`Failed to ${action} agent`, err);
    } finally {
      setActionLoading(false);
    }
  }, [agent]);

  // Delete
  const handleDelete = useCallback(async () => {
    if (!agent) return;
    setActionLoading(true);
    try {
      await deleteAgent(agent.id);
      log.info(`Agent ${agent.id} deleted, navigating to agents list`);
      navigate('/app/agents');
    } catch (err) {
      log.error('Failed to delete agent', err);
      setActionLoading(false);
      setShowDeleteConfirm(false);
    }
  }, [agent, navigate]);

  // Edit callback
  const handleEdited = useCallback((updated: AgentSummary) => {
    setAgent(updated);
    setShowEditModal(false);
  }, []);

  if (loading) {
    return <div className="p-6 text-[var(--text-secondary)]">Loading...</div>;
  }

  if (!agent) {
    return (
      <div className="p-6">
        <Link to="/app/agents" className="mb-4 inline-block text-sm text-[var(--accent-blue)] hover:underline">
          &larr; All Agents
        </Link>
        <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-8 text-center text-sm text-[var(--text-secondary)]">
          Agent not found.
        </div>
      </div>
    );
  }

  const status = agent.status as AgentStatus;
  const canStart = ['created', 'stopped', 'paused', 'error'].includes(status);
  const canPause = status === 'active';
  const canStop = ['active', 'paused', 'error'].includes(status);
  const canEdit = ['created', 'stopped'].includes(status);
  const canDelete = ['created', 'stopped', 'error'].includes(status);

  return (
    <div className="p-6">
      {/* Back link */}
      <Link to="/app/agents" className="mb-4 inline-block text-sm text-[var(--accent-blue)] hover:underline">
        &larr; All Agents
      </Link>

      {/* Header card */}
      <div className="mb-6 rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-semibold">{agent.name}</h1>
            <AgentStatusBadge status={status} />
            <span className={`inline-block rounded-full px-2.5 py-1 text-xs font-medium ${
              agent.paper
                ? 'bg-[var(--accent-blue)]/10 text-[var(--accent-blue)]'
                : 'bg-[var(--accent-green)]/10 text-[var(--accent-green)]'
            }`}>
              {agent.paper ? 'Paper' : 'Live'}
            </span>
          </div>

          {/* Action buttons */}
          <div className="flex items-center gap-2">
            {canEdit && (
              <button
                type="button"
                onClick={() => setShowEditModal(true)}
                className="inline-flex h-8 items-center gap-1.5 rounded-md border border-[var(--border-color)] px-3 text-xs text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-primary)]"
              >
                <Pencil size={13} />
                Edit
              </button>
            )}
            {canDelete && (
              <button
                type="button"
                onClick={() => setShowDeleteConfirm(true)}
                className="inline-flex h-8 items-center gap-1.5 rounded-md border border-[var(--accent-red)]/30 px-3 text-xs text-[var(--accent-red)] transition-colors hover:bg-[var(--accent-red)]/10"
              >
                <Trash2 size={13} />
                Delete
              </button>
            )}
          </div>
        </div>

        {/* Meta row */}
        <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-[var(--text-secondary)]">
          <span className="font-medium text-[var(--text-primary)]">{agent.symbol}</span>
          <span className="text-[var(--border-color)]">|</span>
          <span>{agent.strategy_name ?? `Strategy #${agent.strategy_id}`}</span>
          <span className="text-[var(--border-color)]">|</span>
          <span>{agent.timeframe}</span>
          <span className="text-[var(--border-color)]">|</span>
          <span>${agent.position_size_dollars.toLocaleString()}</span>
        </div>

        {/* Lifecycle buttons */}
        <div className="mt-4 flex items-center gap-2">
          {canStart && (
            <button
              type="button"
              onClick={() => handleLifecycleAction('start')}
              disabled={actionLoading}
              className="inline-flex h-8 items-center gap-1.5 rounded-md bg-[var(--accent-green)] px-4 text-xs font-medium text-white transition-colors hover:bg-[var(--accent-green)]/90 disabled:opacity-50"
            >
              {actionLoading ? <Loader2 size={13} className="animate-spin" /> : <Play size={13} />}
              Start
            </button>
          )}
          {canPause && (
            <button
              type="button"
              onClick={() => handleLifecycleAction('pause')}
              disabled={actionLoading}
              className="inline-flex h-8 items-center gap-1.5 rounded-md bg-[var(--accent-yellow)] px-4 text-xs font-medium text-white transition-colors hover:bg-[var(--accent-yellow)]/90 disabled:opacity-50"
            >
              {actionLoading ? <Loader2 size={13} className="animate-spin" /> : <Pause size={13} />}
              Pause
            </button>
          )}
          {canStop && (
            <button
              type="button"
              onClick={() => handleLifecycleAction('stop')}
              disabled={actionLoading}
              className="inline-flex h-8 items-center gap-1.5 rounded-md border border-[var(--border-color)] px-4 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-primary)] disabled:opacity-50"
            >
              {actionLoading ? <Loader2 size={13} className="animate-spin" /> : <Square size={13} />}
              Stop
            </button>
          )}
        </div>
      </div>

      {/* Error banner */}
      {agent.error_message && (
        <div className="mb-6 flex items-start gap-3 rounded-lg border border-[var(--accent-red)]/30 bg-[var(--accent-red)]/5 px-4 py-3">
          <AlertTriangle size={18} className="mt-0.5 flex-shrink-0 text-[var(--accent-red)]" />
          <div>
            <p className="text-sm font-medium text-[var(--accent-red)]">Agent Error</p>
            <p className="mt-0.5 text-xs text-[var(--text-secondary)]">{agent.error_message}</p>
            {agent.consecutive_errors > 1 && (
              <p className="mt-1 text-xs text-[var(--text-secondary)]">
                {agent.consecutive_errors} consecutive errors
              </p>
            )}
          </div>
        </div>
      )}

      {/* Current position card */}
      {agent.current_position && (
        <div className="mb-6 rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
          <h2 className="mb-2 text-xs font-medium uppercase tracking-wider text-[var(--text-secondary)]">
            Current Position
          </h2>
          <div className="flex items-center gap-4 text-sm">
            <span className={`font-medium ${
              agent.current_position.direction === 'long'
                ? 'text-[var(--accent-green)]'
                : 'text-[var(--accent-red)]'
            }`}>
              {agent.current_position.direction.toUpperCase()}
            </span>
            <span className="text-[var(--text-secondary)]">
              {agent.current_position.quantity} shares
            </span>
            <span className="text-[var(--text-secondary)]">
              @ ${agent.current_position.entry_price.toFixed(2)}
            </span>
            <span className="text-xs text-[var(--text-secondary)]">
              {new Date(agent.current_position.entry_time).toLocaleString()}
            </span>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="mb-4 flex gap-2 border-b border-[var(--border-color)] pb-0">
        {(['orders', 'activity'] as const).map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={`-mb-px border-b-2 px-4 py-2.5 text-sm font-medium transition-colors ${
              tab === t
                ? 'border-[var(--accent-blue)] text-[var(--accent-blue)]'
                : 'border-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
            }`}
          >
            {t === 'orders' ? 'Orders' : 'Activity'}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
        {tab === 'orders' && (
          ordersLoading
            ? <div className="py-8 text-center text-sm text-[var(--text-secondary)]">Loading orders...</div>
            : <AgentOrdersTable orders={orders} />
        )}
        {tab === 'activity' && (
          activitiesLoading
            ? <div className="py-8 text-center text-sm text-[var(--text-secondary)]">Loading activity...</div>
            : <AgentActivityLog activities={activities} />
        )}
      </div>

      {/* Edit modal */}
      <CreateAgentModal
        isOpen={showEditModal}
        onClose={() => setShowEditModal(false)}
        onCreated={handleEdited}
        editAgent={agent}
      />

      {/* Delete confirmation modal */}
      <Modal isOpen={showDeleteConfirm} onClose={() => setShowDeleteConfirm(false)} title="Delete Agent">
        <div className="p-4">
          <p className="text-sm text-[var(--text-secondary)]">
            Are you sure you want to delete <span className="font-medium text-[var(--text-primary)]">{agent.name}</span>?
            This action cannot be undone.
          </p>
          <div className="mt-4 flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setShowDeleteConfirm(false)}
              className="inline-flex h-9 items-center rounded-md border border-[var(--border-color)] px-4 text-xs text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-primary)]"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleDelete}
              disabled={actionLoading}
              className="inline-flex h-9 items-center gap-1.5 rounded-md bg-[var(--accent-red)] px-4 text-xs font-medium text-white transition-colors hover:bg-[var(--accent-red)]/90 disabled:opacity-50"
            >
              {actionLoading && <Loader2 size={14} className="animate-spin" />}
              Delete
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
