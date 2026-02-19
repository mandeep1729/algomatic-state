import type { AgentActivity } from '../../types';

const SEVERITY_DOT: Record<string, string> = {
  info: 'bg-[var(--accent-blue)]',
  warn: 'bg-[var(--accent-yellow)]',
  warning: 'bg-[var(--accent-yellow)]',
  error: 'bg-[var(--accent-red)]',
  critical: 'bg-[var(--accent-red)]',
};

function formatTimestamp(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    second: '2-digit',
  });
}

export function AgentActivityLog({ activities }: { activities: AgentActivity[] }) {
  if (activities.length === 0) {
    return (
      <div className="py-8 text-center text-sm text-[var(--text-secondary)]">
        No activity yet.
      </div>
    );
  }

  return (
    <div className="max-h-[400px] space-y-2 overflow-y-auto pr-1 scrollbar-thin scrollbar-track-transparent scrollbar-thumb-[var(--border-color)]">
      {activities.map((a) => (
        <div
          key={a.id}
          className="flex items-start gap-3 rounded-md border border-[var(--border-color)]/50 px-3 py-2.5"
        >
          {/* Severity dot */}
          <span
            className={`mt-1.5 h-2 w-2 flex-shrink-0 rounded-full ${SEVERITY_DOT[a.severity] ?? SEVERITY_DOT.info}`}
          />

          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className="inline-block rounded px-1.5 py-0.5 text-[10px] font-medium bg-[var(--bg-tertiary)] text-[var(--text-secondary)]">
                {a.activity_type}
              </span>
              <span className="text-[10px] text-[var(--text-secondary)]">
                {formatTimestamp(a.created_at)}
              </span>
            </div>
            <p className="mt-0.5 text-xs text-[var(--text-primary)]">{a.message}</p>
          </div>
        </div>
      ))}
    </div>
  );
}
