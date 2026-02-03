import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import api from '../../api';
import type { TradeDetail as TradeDetailType } from '../../types';
import { DirectionBadge, SourceBadge, StatusBadge } from '../../components/badges';
import EvaluationDisplay from '../../components/EvaluationDisplay';
import { format } from 'date-fns';

export default function TradeDetail() {
  const { tradeId } = useParams<{ tradeId: string }>();
  const [trade, setTrade] = useState<TradeDetailType | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!tradeId) return;
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const res = await api.fetchTradeDetail(tradeId!);
        if (!cancelled) setTrade(res);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load trade');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => { cancelled = true; };
  }, [tradeId]);

  if (loading) {
    return <div className="p-8 text-[var(--text-secondary)]">Loading...</div>;
  }

  if (error || !trade) {
    return (
      <div className="p-8">
        <div className="rounded-lg border border-[var(--accent-red)] bg-[var(--accent-red)]/5 p-4 text-sm text-[var(--accent-red)]">
          {error ?? 'Trade not found'}
        </div>
        <Link to="/app/trades" className="mt-4 inline-block text-sm text-[var(--accent-blue)] hover:underline">
          Back to Trades
        </Link>
      </div>
    );
  }

  return (
    <div className="p-6">
      {/* Back link */}
      <Link to="/app/trades" className="mb-4 inline-block text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)]">
        &larr; Back to Trades
      </Link>

      {/* Header */}
      <div className="mb-6">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold">{trade.symbol}</h1>
          <DirectionBadge direction={trade.direction} />
          <SourceBadge source={trade.source} />
          <StatusBadge status={trade.status} />
          {trade.is_flagged && (
            <span className="rounded bg-[var(--accent-red)]/10 px-2 py-0.5 text-xs text-[var(--accent-red)]">
              {trade.flag_count} flag{trade.flag_count !== 1 ? 's' : ''}
            </span>
          )}
        </div>
        {trade.brokerage && (
          <div className="mt-1 text-xs text-[var(--text-secondary)]">via {trade.brokerage}</div>
        )}
      </div>

      {/* Trade details grid */}
      <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
        <DetailCard label="Entry Price" value={`$${trade.entry_price.toFixed(2)}`} />
        <DetailCard
          label="Exit Price"
          value={trade.exit_price != null ? `$${trade.exit_price.toFixed(2)}` : '--'}
        />
        <DetailCard label="Quantity" value={String(trade.quantity)} />
        <DetailCard label="Timeframe" value={trade.timeframe} />
        <DetailCard
          label="Stop Loss"
          value={trade.stop_loss != null ? `$${trade.stop_loss.toFixed(2)}` : 'None'}
          warn={trade.stop_loss == null}
        />
        <DetailCard
          label="Profit Target"
          value={trade.profit_target != null ? `$${trade.profit_target.toFixed(2)}` : 'None'}
        />
      </div>

      {/* P&L + R:R row */}
      <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <DetailCard
          label="Risk:Reward"
          value={trade.risk_reward_ratio != null ? `${trade.risk_reward_ratio.toFixed(2)}` : '--'}
        />
        <DetailCard
          label="P&L"
          value={trade.pnl != null ? `$${trade.pnl.toFixed(2)}` : '--'}
          accent={trade.pnl != null ? (trade.pnl >= 0 ? 'green' : 'red') : undefined}
        />
        <DetailCard
          label="P&L %"
          value={trade.pnl_pct != null ? `${trade.pnl_pct.toFixed(2)}%` : '--'}
          accent={trade.pnl_pct != null ? (trade.pnl_pct >= 0 ? 'green' : 'red') : undefined}
        />
        <DetailCard
          label="Entry Time"
          value={formatTime(trade.entry_time)}
        />
      </div>

      {/* Tags */}
      {trade.tags.length > 0 && (
        <div className="mb-6 flex flex-wrap gap-2">
          {trade.tags.map((tag) => (
            <span
              key={tag}
              className="rounded-full border border-[var(--border-color)] bg-[var(--bg-tertiary)] px-2.5 py-1 text-xs text-[var(--text-secondary)]"
            >
              {tag.replace(/_/g, ' ')}
            </span>
          ))}
        </div>
      )}

      {/* Notes */}
      {trade.notes && (
        <div className="mb-6 rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
          <div className="mb-1 text-xs font-medium text-[var(--text-secondary)]">Notes</div>
          <p className="text-sm">{trade.notes}</p>
        </div>
      )}

      {/* Evaluation */}
      <div className="mt-8">
        <h2 className="mb-4 text-lg font-semibold">Evaluation</h2>
        {trade.evaluation ? (
          <EvaluationDisplay evaluation={trade.evaluation} />
        ) : (
          <div className="rounded-lg border border-dashed border-[var(--border-color)] bg-[var(--bg-secondary)] p-8 text-center text-sm text-[var(--text-secondary)]">
            This trade has not been evaluated yet.
          </div>
        )}
      </div>
    </div>
  );
}

function DetailCard({
  label,
  value,
  accent,
  warn,
}: {
  label: string;
  value: string;
  accent?: 'green' | 'red';
  warn?: boolean;
}) {
  const valueColor = accent === 'green'
    ? 'text-[var(--accent-green)]'
    : accent === 'red'
    ? 'text-[var(--accent-red)]'
    : warn
    ? 'text-[var(--accent-yellow)]'
    : 'text-[var(--text-primary)]';

  return (
    <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] px-3 py-2.5">
      <div className="text-[10px] font-medium uppercase tracking-wider text-[var(--text-secondary)]">
        {label}
      </div>
      <div className={`mt-0.5 font-mono text-sm font-medium ${valueColor}`}>
        {value}
      </div>
    </div>
  );
}

function formatTime(iso: string | null): string {
  if (!iso) return '--';
  try {
    return format(new Date(iso), 'MMM d, yyyy HH:mm');
  } catch {
    return iso;
  }
}
