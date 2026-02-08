import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search } from 'lucide-react';
import api from '../../api';
import { DataTable, type Column } from '../../components/DataTable';
import { OverallLabelBadge } from '../../components/campaigns/OverallLabelBadge';
import type { CampaignSummary } from '../../types';

function formatDateRange(openedAt: string, closedAt?: string): string {
  const opened = new Date(openedAt).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
  });
  if (!closedAt) return `${opened} - Open`;
  const closed = new Date(closedAt).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
  });
  return `${opened} - ${closed}`;
}

/**
 * Format quantity display with leg breakdown.
 * Shows: total_qty (leg1_qty+leg2_qty-leg3_qty...)
 * Example: For legs [+3, -1, -2], displays: 0 (+3-1-2)
 */
function formatQtyWithLegs(legQuantities: number[]): string {
  if (!legQuantities || legQuantities.length === 0) {
    return '0';
  }

  const total = legQuantities.reduce((sum, qty) => sum + qty, 0);

  // Build leg breakdown string: first leg uses + for positive or - for negative,
  // subsequent legs use +/- as separator based on sign
  const legParts = legQuantities.map((qty) => {
    const absQty = Math.abs(qty);
    return qty >= 0 ? `+${absQty}` : `-${absQty}`;
  });

  const breakdown = legParts.join('');
  return `${total} (${breakdown})`;
}

// Define table columns
const columns: Column<CampaignSummary>[] = [
  {
    key: 'campaign',
    header: 'Campaign',
    hideable: false,
    render: (campaign) => (
      <div>
        <div className="font-medium text-[var(--text-primary)]">
          {campaign.symbol}{' '}
          <span
            className={`text-xs font-medium ${
              campaign.direction === 'long'
                ? 'text-[var(--accent-green)]'
                : 'text-[var(--accent-red)]'
            }`}
          >
            {campaign.direction.toUpperCase()}
          </span>
        </div>
        <div className="mt-0.5 text-xs text-[var(--text-secondary)]">
          {formatDateRange(campaign.openedAt, campaign.closedAt)}
        </div>
      </div>
    ),
  },
  {
    key: 'legs',
    header: 'Legs',
    render: (campaign) => (
      <span className="text-[var(--text-secondary)]">{campaign.legsCount}</span>
    ),
  },
  {
    key: 'qty',
    header: 'Qty',
    render: (campaign) => (
      <span className="text-[var(--text-secondary)]">
        {formatQtyWithLegs(campaign.legQuantities)}
      </span>
    ),
  },
  {
    key: 'status',
    header: 'Status',
    render: (campaign) => (
      <span
        className={`inline-block rounded-full px-2.5 py-1 text-xs font-medium ${
          campaign.status === 'open'
            ? 'bg-[var(--accent-blue)]/10 text-[var(--accent-blue)]'
            : 'bg-[var(--bg-tertiary)] text-[var(--text-secondary)]'
        }`}
      >
        {campaign.status.charAt(0).toUpperCase() + campaign.status.slice(1)}
      </span>
    ),
  },
  {
    key: 'evaluation',
    header: 'Evaluation',
    render: (campaign) => (
      <div className="flex flex-wrap items-center gap-1.5">
        <OverallLabelBadge label={campaign.overallLabel} />
        {campaign.keyFlags.slice(0, 2).map((flag) => (
          <span
            key={flag}
            className="inline-block rounded px-2 py-0.5 text-[10px] font-medium bg-[var(--accent-blue)]/10 text-[var(--accent-blue)]"
          >
            {flag.replace(/_/g, ' ')}
          </span>
        ))}
      </div>
    ),
  },
  {
    key: 'strategy',
    header: 'Strategy',
    render: (campaign) => {
      if (!campaign.strategies || campaign.strategies.length === 0) {
        return <span className="text-[var(--text-secondary)]">-</span>;
      }
      return (
        <span className="text-[var(--text-secondary)]">
          {campaign.strategies.join(', ')}
        </span>
      );
    },
  },
];

export default function Campaigns() {
  const navigate = useNavigate();
  const [campaigns, setCampaigns] = useState<CampaignSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [symbolFilter, setSymbolFilter] = useState('');

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      try {
        const data = await api.fetchCampaigns();
        if (!cancelled) setCampaigns(data);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => { cancelled = true; };
  }, []);

  const filtered = useMemo(() => {
    const query = symbolFilter.trim().toUpperCase();
    if (!query) return campaigns;
    return campaigns.filter((c) => c.symbol.includes(query));
  }, [campaigns, symbolFilter]);

  const handleRowClick = (campaign: CampaignSummary) => {
    navigate(`/app/campaigns/${campaign.campaignId}`);
  };

  return (
    <div className="p-6">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Campaigns</h1>
        <span className="text-sm text-[var(--text-secondary)]">
          {filtered.length} campaign{filtered.length !== 1 ? 's' : ''}
        </span>
      </div>

      {/* Search bar */}
      <div className="mb-4">
        <div className="relative">
          <Search
            size={13}
            className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--text-secondary)]"
          />
          <input
            type="text"
            placeholder="Search symbol..."
            value={symbolFilter}
            onChange={(e) => setSymbolFilter(e.target.value)}
            className="h-8 w-48 rounded-md border border-[var(--border-color)] bg-[var(--bg-primary)] pl-8 pr-3 text-xs text-[var(--text-primary)] placeholder:text-[var(--text-secondary)] focus:border-[var(--accent-blue)] focus:outline-none"
          />
        </div>
      </div>

      {/* DataTable with column visibility persistence */}
      <DataTable
        tableName="campaigns"
        columns={columns}
        data={filtered}
        loading={loading}
        emptyMessage="No campaigns match your search."
        getRowKey={(campaign) => campaign.campaignId}
        onRowClick={handleRowClick}
      />
    </div>
  );
}
