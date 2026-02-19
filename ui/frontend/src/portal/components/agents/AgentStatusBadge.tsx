import type { AgentStatus } from '../../types';

const STATUS_STYLES: Record<AgentStatus, string> = {
  active: 'bg-[var(--accent-green)]/10 text-[var(--accent-green)]',
  paused: 'bg-[var(--accent-yellow)]/10 text-[var(--accent-yellow)]',
  created: 'bg-[var(--bg-tertiary)] text-[var(--text-secondary)]',
  stopped: 'bg-[var(--bg-tertiary)] text-[var(--text-secondary)]',
  error: 'bg-[var(--accent-red)]/10 text-[var(--accent-red)]',
};

export function AgentStatusBadge({ status }: { status: AgentStatus }) {
  const style = STATUS_STYLES[status] ?? STATUS_STYLES.created;
  return (
    <span className={`inline-block rounded-full px-2.5 py-1 text-xs font-medium ${style}`}>
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  );
}
