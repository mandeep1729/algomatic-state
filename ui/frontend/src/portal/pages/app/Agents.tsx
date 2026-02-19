import { useEffect, useMemo, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus } from 'lucide-react';
import { fetchAgents } from '../../api';
import { DataTable, type Column } from '../../components/DataTable';
import { StatCard } from '../../components/ui/StatCard';
import { AgentStatusBadge } from '../../components/agents/AgentStatusBadge';
import { CreateAgentModal } from '../../components/agents/CreateAgentModal';
import type { AgentSummary, AgentStatus } from '../../types';
import { createLogger } from '../../utils/logger';

const log = createLogger('Agents');

function formatTime(iso: string | null): string {
  if (!iso) return '-';
  return new Date(iso).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

export default function Agents() {
  const navigate = useNavigate();
  const [agents, setAgents] = useState<AgentSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);

  const loadAgents = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchAgents();
      setAgents(data);
    } catch (err) {
      log.error('Failed to load agents', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAgents();
  }, [loadAgents]);

  // Stats
  const stats = useMemo(() => {
    const total = agents.length;
    const active = agents.filter((a) => a.status === 'active').length;
    const paused = agents.filter((a) => a.status === 'paused').length;
    const errors = agents.filter((a) => a.status === 'error').length;
    return { total, active, paused, errors };
  }, [agents]);

  // Columns
  const columns: Column<AgentSummary>[] = useMemo(() => [
    {
      key: 'agent',
      header: 'Agent',
      hideable: false,
      filterFn: (agent, text) => {
        const q = text.toLowerCase();
        return (
          agent.name.toLowerCase().includes(q) ||
          agent.symbol.toLowerCase().includes(q) ||
          (agent.strategy_name ?? '').toLowerCase().includes(q)
        );
      },
      render: (agent) => (
        <div>
          <div className="font-medium text-[var(--text-primary)]">{agent.name}</div>
          <div className="mt-0.5 flex items-center gap-1.5 text-xs text-[var(--text-secondary)]">
            <span className="font-medium text-[var(--text-primary)]">{agent.symbol}</span>
            {agent.strategy_name && (
              <>
                <span className="text-[var(--border-color)]">/</span>
                <span>{agent.strategy_name}</span>
              </>
            )}
          </div>
        </div>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      filterFn: (agent, text) => agent.status.toLowerCase().includes(text.toLowerCase()),
      render: (agent) => <AgentStatusBadge status={agent.status as AgentStatus} />,
    },
    {
      key: 'timeframe',
      header: 'Timeframe',
      filterFn: (agent, text) => agent.timeframe.toLowerCase().includes(text.toLowerCase()),
      render: (agent) => (
        <span className="text-[var(--text-secondary)]">{agent.timeframe}</span>
      ),
    },
    {
      key: 'position',
      header: 'Position',
      render: (agent) => {
        if (!agent.current_position) {
          return <span className="text-[var(--text-secondary)]">-</span>;
        }
        const pos = agent.current_position;
        return (
          <div className="text-xs">
            <span className={`font-medium ${pos.direction === 'long' ? 'text-[var(--accent-green)]' : 'text-[var(--accent-red)]'}`}>
              {pos.direction.toUpperCase()}
            </span>
            <span className="ml-1 text-[var(--text-secondary)]">
              {pos.quantity} @ ${pos.entry_price.toFixed(2)}
            </span>
          </div>
        );
      },
    },
    {
      key: 'lastSignal',
      header: 'Last Signal',
      filterFn: (agent, text) => (agent.last_signal ?? '').toLowerCase().includes(text.toLowerCase()),
      render: (agent) => (
        <span className="text-[var(--text-secondary)]">{agent.last_signal ?? '-'}</span>
      ),
    },
    {
      key: 'lastRun',
      header: 'Last Run',
      render: (agent) => (
        <span className="text-[var(--text-secondary)]">{formatTime(agent.last_run_at)}</span>
      ),
    },
    {
      key: 'mode',
      header: 'Mode',
      filterFn: (agent, text) => {
        const mode = agent.paper ? 'paper' : 'live';
        return mode.includes(text.toLowerCase());
      },
      render: (agent) => (
        <span
          className={`inline-block rounded-full px-2.5 py-1 text-xs font-medium ${
            agent.paper
              ? 'bg-[var(--accent-blue)]/10 text-[var(--accent-blue)]'
              : 'bg-[var(--accent-green)]/10 text-[var(--accent-green)]'
          }`}
        >
          {agent.paper ? 'Paper' : 'Live'}
        </span>
      ),
    },
  ], []);

  const handleAgentCreated = useCallback(() => {
    loadAgents();
  }, [loadAgents]);

  return (
    <div className="p-6">
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Trading Agents</h1>
        <button
          type="button"
          onClick={() => setShowCreateModal(true)}
          className="inline-flex h-9 items-center gap-1.5 rounded-md bg-[var(--accent-blue)] px-4 text-xs font-medium text-white transition-colors hover:bg-[var(--accent-blue)]/90"
        >
          <Plus size={14} />
          New Agent
        </button>
      </div>

      {/* Stats row */}
      <div className="mb-6 grid grid-cols-4 gap-4">
        <StatCard label="Total Agents" value={stats.total} />
        <StatCard label="Active" value={stats.active} accent="green" />
        <StatCard label="Paused" value={stats.paused} accent="yellow" />
        <StatCard label="Errors" value={stats.errors} accent={stats.errors > 0 ? 'red' : undefined} />
      </div>

      {/* DataTable */}
      <DataTable
        tableName="agents"
        columns={columns}
        data={agents}
        loading={loading}
        emptyMessage="No agents yet. Create one to get started."
        getRowKey={(agent) => String(agent.id)}
        onRowClick={(agent) => navigate(`/app/agents/${agent.id}`)}
      />

      {/* Create modal */}
      <CreateAgentModal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        onCreated={handleAgentCreated}
      />
    </div>
  );
}
