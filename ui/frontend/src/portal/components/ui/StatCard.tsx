export function StatCard({
  label,
  value,
  sub,
  accent,
}: {
  label: string;
  value: string | number;
  sub?: string;
  accent?: 'red' | 'green' | 'yellow';
}) {
  const colorClass = accent === 'red'
    ? 'text-[var(--accent-red)]'
    : accent === 'green'
      ? 'text-[var(--accent-green)]'
      : accent === 'yellow'
        ? 'text-[var(--accent-yellow)]'
        : 'text-[var(--text-primary)]';

  return (
    <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] px-4 py-3">
      <div className="text-[10px] font-medium uppercase tracking-wider text-[var(--text-secondary)]">{label}</div>
      <div className="mt-1 flex items-baseline gap-1.5">
        <span className={`text-xl font-semibold ${colorClass}`}>{value}</span>
        {sub && <span className="text-xs text-[var(--text-secondary)]">{sub}</span>}
      </div>
    </div>
  );
}
