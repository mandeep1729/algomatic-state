import type { AgentOrder } from '../../types';

function formatTimestamp(iso: string | null): string {
  if (!iso) return '-';
  return new Date(iso).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

const ORDER_STATUS_STYLES: Record<string, string> = {
  filled: 'bg-[var(--accent-green)]/10 text-[var(--accent-green)]',
  partially_filled: 'bg-[var(--accent-yellow)]/10 text-[var(--accent-yellow)]',
  cancelled: 'bg-[var(--bg-tertiary)] text-[var(--text-secondary)]',
  rejected: 'bg-[var(--accent-red)]/10 text-[var(--accent-red)]',
  pending: 'bg-[var(--accent-blue)]/10 text-[var(--accent-blue)]',
  new: 'bg-[var(--accent-blue)]/10 text-[var(--accent-blue)]',
};

export function AgentOrdersTable({ orders }: { orders: AgentOrder[] }) {
  if (orders.length === 0) {
    return (
      <div className="py-8 text-center text-sm text-[var(--text-secondary)]">
        No orders yet.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="text-left text-[10px] font-medium uppercase tracking-wider text-[var(--text-secondary)]">
            <th className="px-3 py-2">Side</th>
            <th className="px-3 py-2">Qty</th>
            <th className="px-3 py-2">Type</th>
            <th className="px-3 py-2">Status</th>
            <th className="px-3 py-2">Price</th>
            <th className="px-3 py-2">Signal</th>
            <th className="px-3 py-2">Submitted</th>
            <th className="px-3 py-2">Filled</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-[var(--border-color)]/50">
          {orders.map((order) => (
            <tr key={order.id} className="transition-colors hover:bg-[var(--bg-tertiary)]/30">
              <td className="px-3 py-2">
                <span
                  className={`font-medium ${
                    order.side === 'buy'
                      ? 'text-[var(--accent-green)]'
                      : 'text-[var(--accent-red)]'
                  }`}
                >
                  {order.side.toUpperCase()}
                </span>
              </td>
              <td className="px-3 py-2 text-[var(--text-secondary)]">{order.quantity}</td>
              <td className="px-3 py-2 text-[var(--text-secondary)]">{order.order_type}</td>
              <td className="px-3 py-2">
                <span className={`inline-block rounded px-1.5 py-0.5 text-[10px] font-medium ${ORDER_STATUS_STYLES[order.status] ?? ORDER_STATUS_STYLES.pending}`}>
                  {order.status}
                </span>
              </td>
              <td className="px-3 py-2 text-[var(--text-secondary)]">
                {order.filled_avg_price != null
                  ? `$${order.filled_avg_price.toFixed(2)}`
                  : order.limit_price != null
                    ? `$${order.limit_price.toFixed(2)}`
                    : '-'}
              </td>
              <td className="px-3 py-2 text-[var(--text-secondary)]">
                {order.signal_direction ?? '-'}
              </td>
              <td className="px-3 py-2 text-[var(--text-secondary)]">{formatTimestamp(order.submitted_at)}</td>
              <td className="px-3 py-2 text-[var(--text-secondary)]">{formatTimestamp(order.filled_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
