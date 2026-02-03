import type { TradeSource, TradeStatus, Severity } from '../types';

export function DirectionBadge({ direction }: { direction: string }) {
  const isLong = direction === 'long';
  return (
    <span
      className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${
        isLong
          ? 'bg-[var(--accent-green)]/10 text-[var(--accent-green)]'
          : 'bg-[var(--accent-red)]/10 text-[var(--accent-red)]'
      }`}
    >
      {direction.toUpperCase()}
    </span>
  );
}

export function SourceBadge({ source }: { source: TradeSource }) {
  const colors: Record<TradeSource, string> = {
    synced: 'text-[var(--accent-blue)]',
    manual: 'text-[var(--accent-purple)]',
    csv: 'text-[var(--text-secondary)]',
    proposed: 'text-[var(--accent-yellow)]',
  };

  return (
    <span className={`text-xs ${colors[source]}`}>
      {source}
    </span>
  );
}

export function StatusBadge({ status }: { status: TradeStatus }) {
  const styles: Record<TradeStatus, string> = {
    open: 'bg-[var(--accent-green)]/10 text-[var(--accent-green)]',
    closed: 'bg-[var(--bg-tertiary)] text-[var(--text-secondary)]',
    proposed: 'bg-[var(--accent-yellow)]/10 text-[var(--accent-yellow)]',
  };

  return (
    <span className={`inline-block rounded px-2 py-0.5 text-xs ${styles[status]}`}>
      {status}
    </span>
  );
}

export function SeverityBadge({ severity }: { severity: Severity }) {
  const styles: Record<Severity, string> = {
    info: 'bg-[var(--accent-blue)]/10 text-[var(--accent-blue)]',
    warning: 'bg-[var(--accent-yellow)]/10 text-[var(--accent-yellow)]',
    critical: 'bg-[var(--accent-red)]/10 text-[var(--accent-red)]',
    blocker: 'bg-[var(--accent-red)]/20 text-[var(--accent-red)] font-medium',
  };

  return (
    <span className={`inline-block rounded px-2 py-0.5 text-xs ${styles[severity]}`}>
      {severity}
    </span>
  );
}

const SEVERITY_ICONS: Record<Severity, string> = {
  info: '\u2139',      // i
  warning: '\u26A0',   // triangle
  critical: '\u2716',  // x mark
  blocker: '\u26D4',   // no entry
};

export function SeverityIcon({ severity }: { severity: Severity }) {
  const colors: Record<Severity, string> = {
    info: 'text-[var(--accent-blue)]',
    warning: 'text-[var(--accent-yellow)]',
    critical: 'text-[var(--accent-red)]',
    blocker: 'text-[var(--accent-red)]',
  };

  return (
    <span className={colors[severity]} title={severity}>
      {SEVERITY_ICONS[severity]}
    </span>
  );
}
