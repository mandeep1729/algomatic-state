import { useEffect, useMemo, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, AlertTriangle, X, Loader2, ExternalLink, Trash2, ChevronDown, ChevronRight } from 'lucide-react';
import api from '../../api';
import { bulkUpdateLegStrategy, deleteCampaign, fetchOrphanedLegs } from '../../api';
import { fetchStrategies } from '../../api/client';
import { DataTable, type Column } from '../../components/DataTable';
import { OverallLabelBadge } from '../../components/campaigns/OverallLabelBadge';
import type { CampaignSummary, CampaignDetail, StrategyDefinition, CampaignLeg, OrphanedLegGroup, OrphanedLeg } from '../../types';

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

function formatLegDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
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

/** Get the strategy name for a leg from its decision context */
function getLegStrategy(detail: CampaignDetail, legId: string): string {
  const ctx = detail.contextsByLeg[legId];
  if (!ctx?.strategyTags?.length) return '-';
  return ctx.strategyTags.join(', ');
}

// Define table columns
const columns: Column<CampaignSummary>[] = [
  {
    key: 'campaign',
    header: 'Campaign',
    hideable: false,
    filterFn: (campaign, filterText) => {
      const text = filterText.toLowerCase();
      return (
        campaign.symbol.toLowerCase().includes(text) ||
        campaign.direction.toLowerCase().includes(text) ||
        formatDateRange(campaign.openedAt, campaign.closedAt).toLowerCase().includes(text)
      );
    },
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
    filterFn: (campaign, filterText) =>
      String(campaign.legsCount).includes(filterText),
    render: (campaign) => (
      <span className="text-[var(--text-secondary)]">{campaign.legsCount}</span>
    ),
  },
  {
    key: 'qty',
    header: 'Qty',
    filterFn: (campaign, filterText) =>
      formatQtyWithLegs(campaign.legQuantities).includes(filterText),
    render: (campaign) => (
      <span className="text-[var(--text-secondary)]">
        {formatQtyWithLegs(campaign.legQuantities)}
      </span>
    ),
  },
  {
    key: 'status',
    header: 'Status',
    filterFn: (campaign, filterText) =>
      campaign.status.toLowerCase().includes(filterText.toLowerCase()),
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
    filterFn: (campaign, filterText) => {
      const text = filterText.toLowerCase();
      return (
        campaign.overallLabel.toLowerCase().includes(text) ||
        campaign.keyFlags.some((f) => f.replace(/_/g, ' ').toLowerCase().includes(text))
      );
    },
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
    filterFn: (campaign, filterText) => {
      if (!campaign.strategies || campaign.strategies.length === 0) return false;
      const text = filterText.toLowerCase();
      return campaign.strategies.some((s) => s.toLowerCase().includes(text));
    },
    render: (campaign) => {
      if (!campaign.strategies || campaign.strategies.length === 0) {
        return <span className="text-[var(--text-secondary)]">-</span>;
      }
      return (
        <div className="flex flex-wrap items-center gap-1">
          {campaign.strategies.map((strategy) => (
            <span
              key={strategy}
              className="inline-block rounded px-2 py-0.5 text-[10px] font-medium bg-[var(--accent-green)]/10 text-[var(--accent-green)]"
            >
              {strategy}
            </span>
          ))}
        </div>
      );
    },
  },
  {
    key: 'campaignId',
    header: 'Campaign ID',
    filterFn: (campaign, filterText) =>
      campaign.campaignId.includes(filterText),
    render: (campaign) => (
      <span className="text-[11px] text-[var(--text-secondary)]/50 font-mono">
        {campaign.campaignId}
      </span>
    ),
  },
  {
    key: 'orderIds',
    header: 'Order IDs',
    filterFn: (campaign, filterText) => {
      const ids = campaign.orderIds ?? [];
      const text = filterText.toLowerCase();
      return ids.some((id) => id.toLowerCase().includes(text));
    },
    render: (campaign) => {
      const ids = campaign.orderIds ?? [];
      if (ids.length === 0) {
        return <span className="text-[11px] text-[var(--text-secondary)]/50">-</span>;
      }
      return (
        <div className="flex flex-col gap-0.5">
          {ids.map((id) => (
            <span key={id} className="text-[11px] text-[var(--text-secondary)]/50 font-mono truncate max-w-[140px]" title={id}>
              {id}
            </span>
          ))}
        </div>
      );
    },
  },
];

export default function Campaigns() {
  const navigate = useNavigate();
  const [campaigns, setCampaigns] = useState<CampaignSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [symbolFilter, setSymbolFilter] = useState('');
  const [uncategorizedCount, setUncategorizedCount] = useState(0);
  const [bannerDismissed, setBannerDismissed] = useState(false);

  // Expansion state
  const [expandedCampaignIds, setExpandedCampaignIds] = useState<Set<string>>(new Set());
  const [detailCache, setDetailCache] = useState<Record<string, CampaignDetail>>({});
  const [detailLoading, setDetailLoading] = useState<Set<string>>(new Set());

  // Bulk edit state
  const [selectedLegIds, setSelectedLegIds] = useState<Set<string>>(new Set());
  const [bulkStrategyId, setBulkStrategyId] = useState<string>('');
  const [strategies, setStrategies] = useState<StrategyDefinition[]>([]);
  const [strategiesLoading, setStrategiesLoading] = useState(false);
  const [bulkApplying, setBulkApplying] = useState(false);
  const [bulkError, setBulkError] = useState<string | null>(null);
  const [bulkSuccess, setBulkSuccess] = useState<string | null>(null);

  // Orphaned legs state
  const [orphanedGroups, setOrphanedGroups] = useState<OrphanedLegGroup[]>([]);
  const [expandedOrphanGroups, setExpandedOrphanGroups] = useState<Set<string>>(new Set());
  const [deletingCampaign, setDeletingCampaign] = useState<string | null>(null);

  const hasSelection = selectedLegIds.size > 0;

  // Load campaigns + orphaned legs
  const loadCampaigns = useCallback(async () => {
    setLoading(true);
    try {
      const [data, count, orphaned] = await Promise.all([
        api.fetchCampaigns(),
        api.fetchUncategorizedCount(),
        fetchOrphanedLegs(),
      ]);
      setCampaigns(data);
      setUncategorizedCount(count);
      setOrphanedGroups(orphaned);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadCampaigns();
  }, [loadCampaigns]);

  // Lazy-load campaign detail on expand
  const fetchDetail = useCallback(async (campaignId: string) => {
    // Already cached
    if (detailCache[campaignId]) return;

    setDetailLoading((prev) => new Set(prev).add(campaignId));
    try {
      const detail = await api.fetchCampaignDetail(campaignId);
      setDetailCache((prev) => ({ ...prev, [campaignId]: detail }));
    } catch (err) {
      console.error(`[Campaigns] Failed to load detail for ${campaignId}:`, err);
    } finally {
      setDetailLoading((prev) => {
        const next = new Set(prev);
        next.delete(campaignId);
        return next;
      });
    }
  }, [detailCache]);

  // Handle expansion changes — trigger lazy load on first expand
  const handleExpandChange = useCallback((keys: Set<string>) => {
    // Find newly expanded campaigns
    for (const key of keys) {
      if (!expandedCampaignIds.has(key) && !detailCache[key]) {
        fetchDetail(key);
      }
    }
    setExpandedCampaignIds(keys);
  }, [expandedCampaignIds, detailCache, fetchDetail]);

  // Load strategies lazily when selection starts
  useEffect(() => {
    if (!hasSelection || strategies.length > 0) return;

    let cancelled = false;
    setStrategiesLoading(true);

    async function load() {
      try {
        const data = await fetchStrategies();
        if (!cancelled) setStrategies(data);
      } catch (err) {
        console.error('[Campaigns] Failed to load strategies:', err);
      } finally {
        if (!cancelled) setStrategiesLoading(false);
      }
    }

    load();
    return () => { cancelled = true; };
  }, [hasSelection, strategies.length]);

  // Bulk edit handlers
  const handleClearSelection = useCallback(() => {
    setSelectedLegIds(new Set());
    setBulkStrategyId('');
    setBulkError(null);
    setBulkSuccess(null);
  }, []);

  const handleBulkApply = useCallback(async () => {
    if (!bulkStrategyId || selectedLegIds.size === 0) return;

    setBulkApplying(true);
    setBulkError(null);
    setBulkSuccess(null);

    try {
      const legIds = Array.from(selectedLegIds).map((id) => parseInt(id, 10));
      const strategyId = parseInt(bulkStrategyId, 10);

      const result = await bulkUpdateLegStrategy({
        leg_ids: legIds,
        strategy_id: strategyId,
      });

      const strategyName = strategies.find((s) => s.id === bulkStrategyId)?.name ?? 'selected strategy';
      setBulkSuccess(
        `Updated ${result.updated_count} leg${result.updated_count !== 1 ? 's' : ''} to "${strategyName}"` +
        (result.skipped_count > 0 ? ` (${result.skipped_count} skipped)` : ''),
      );

      // Invalidate detail cache for affected campaigns
      const affectedCampaignIds = new Set<string>();
      for (const legId of selectedLegIds) {
        for (const [cid, detail] of Object.entries(detailCache)) {
          if (detail.legs.some((l) => l.legId === legId)) {
            affectedCampaignIds.add(cid);
          }
        }
      }
      // Clear cache entries so they re-fetch
      setDetailCache((prev) => {
        const next = { ...prev };
        for (const cid of affectedCampaignIds) {
          delete next[cid];
        }
        return next;
      });
      // Re-fetch details for still-expanded affected campaigns
      for (const cid of affectedCampaignIds) {
        if (expandedCampaignIds.has(cid)) {
          fetchDetail(cid);
        }
      }

      // Refresh campaigns list + orphaned legs and clear selection
      await loadCampaigns();
      setSelectedLegIds(new Set());
      setBulkStrategyId('');
    } catch (err) {
      console.error('[Campaigns] Bulk leg update failed:', err);
      setBulkError(err instanceof Error ? err.message : 'Failed to apply bulk update');
    } finally {
      setBulkApplying(false);
    }
  }, [bulkStrategyId, selectedLegIds, strategies, detailCache, expandedCampaignIds, fetchDetail, loadCampaigns]);

  // Delete campaign handler
  const handleDeleteCampaign = useCallback(async (campaignId: string) => {
    if (!window.confirm('Delete this campaign? Legs will be preserved as orphaned legs.')) {
      return;
    }

    setDeletingCampaign(campaignId);
    try {
      await deleteCampaign(campaignId);

      // Remove from detail cache
      setDetailCache((prev) => {
        const next = { ...prev };
        delete next[campaignId];
        return next;
      });

      // Collapse it
      setExpandedCampaignIds((prev) => {
        const next = new Set(prev);
        next.delete(campaignId);
        return next;
      });

      // Refresh campaigns + orphaned legs
      await loadCampaigns();
    } catch (err) {
      console.error('[Campaigns] Delete failed:', err);
      setBulkError(err instanceof Error ? err.message : 'Failed to delete campaign');
    } finally {
      setDeletingCampaign(null);
    }
  }, [loadCampaigns]);

  // Toggle leg selection
  const toggleLegSelection = useCallback((legId: string) => {
    setSelectedLegIds((prev) => {
      const next = new Set(prev);
      if (next.has(legId)) {
        next.delete(legId);
      } else {
        next.add(legId);
      }
      return next;
    });
  }, []);

  // Toggle all legs for a campaign
  const toggleAllLegsForCampaign = useCallback((legs: CampaignLeg[]) => {
    setSelectedLegIds((prev) => {
      const legIds = legs.map((l) => l.legId);
      const allSelected = legIds.every((id) => prev.has(id));
      const next = new Set(prev);
      if (allSelected) {
        for (const id of legIds) next.delete(id);
      } else {
        for (const id of legIds) next.add(id);
      }
      return next;
    });
  }, []);

  // Toggle all orphaned legs in a group
  const toggleAllOrphanedLegs = useCallback((legs: OrphanedLeg[]) => {
    setSelectedLegIds((prev) => {
      const legIds = legs.map((l) => l.legId);
      const allSelected = legIds.every((id) => prev.has(id));
      const next = new Set(prev);
      if (allSelected) {
        for (const id of legIds) next.delete(id);
      } else {
        for (const id of legIds) next.add(id);
      }
      return next;
    });
  }, []);

  // Toggle orphan group expansion
  const toggleOrphanGroup = useCallback((key: string) => {
    setExpandedOrphanGroups((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  }, []);

  const filtered = useMemo(() => {
    const query = symbolFilter.trim().toUpperCase();
    if (!query) return campaigns;
    return campaigns.filter((c) => c.symbol.includes(query));
  }, [campaigns, symbolFilter]);

  // Render expanded row content
  const renderExpandedRow = useCallback((campaign: CampaignSummary) => {
    const isLoading = detailLoading.has(campaign.campaignId);
    const detail = detailCache[campaign.campaignId];
    const isDeleting = deletingCampaign === campaign.campaignId;

    if (isLoading || !detail) {
      return (
        <div className="flex items-center gap-2 px-6 py-4 text-xs text-[var(--text-secondary)]">
          <Loader2 size={14} className="animate-spin" />
          Loading legs...
        </div>
      );
    }

    const legs = detail.legs;
    const allLegsSelected = legs.length > 0 && legs.every((l) => selectedLegIds.has(l.legId));

    return (
      <div className="px-4 py-3">
        {/* Legs mini table */}
        <table className="w-full text-xs">
          <thead>
            <tr className="text-left text-[10px] font-medium uppercase tracking-wider text-[var(--text-secondary)]">
              <th className="w-8 px-2 py-1.5">
                <input
                  type="checkbox"
                  checked={allLegsSelected}
                  onChange={() => toggleAllLegsForCampaign(legs)}
                  className="h-3 w-3 rounded border-[var(--border-color)] text-[var(--accent-blue)] focus:ring-[var(--accent-blue)]"
                  aria-label="Select all legs"
                />
              </th>
              <th className="px-3 py-1.5">Type</th>
              <th className="px-3 py-1.5">Side</th>
              <th className="px-3 py-1.5">Qty</th>
              <th className="px-3 py-1.5">Price</th>
              <th className="px-3 py-1.5">Date</th>
              <th className="px-3 py-1.5">Strategy</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--border-color)]/50">
            {legs.map((leg) => {
              const isLegSelected = selectedLegIds.has(leg.legId);
              return (
                <tr
                  key={leg.legId}
                  className={`transition-colors ${isLegSelected ? 'bg-[var(--accent-blue)]/5' : ''}`}
                >
                  <td className="w-8 px-2 py-2">
                    <input
                      type="checkbox"
                      checked={isLegSelected}
                      onChange={() => toggleLegSelection(leg.legId)}
                      className="h-3 w-3 rounded border-[var(--border-color)] text-[var(--accent-blue)] focus:ring-[var(--accent-blue)]"
                      aria-label={`Select leg ${leg.legId}`}
                    />
                  </td>
                  <td className="px-3 py-2">
                    <span className="inline-block rounded px-1.5 py-0.5 text-[10px] font-medium bg-[var(--bg-tertiary)] text-[var(--text-secondary)]">
                      {leg.legType}
                    </span>
                  </td>
                  <td className="px-3 py-2">
                    <span
                      className={`font-medium ${
                        leg.side === 'buy'
                          ? 'text-[var(--accent-green)]'
                          : 'text-[var(--accent-red)]'
                      }`}
                    >
                      {leg.side.toUpperCase()}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-[var(--text-secondary)]">
                    {leg.quantity}
                  </td>
                  <td className="px-3 py-2 text-[var(--text-secondary)]">
                    ${leg.avgPrice.toFixed(2)}
                  </td>
                  <td className="px-3 py-2 text-[var(--text-secondary)]">
                    {formatLegDate(leg.startedAt)}
                  </td>
                  <td className="px-3 py-2 text-[var(--text-secondary)]">
                    {getLegStrategy(detail, leg.legId)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>

        {/* Action row: View detail + Delete */}
        <div className="mt-2 flex items-center gap-4 px-2">
          <button
            type="button"
            onClick={() => navigate(`/app/campaigns/${campaign.campaignId}`)}
            className="inline-flex items-center gap-1 text-xs text-[var(--accent-blue)] hover:underline"
          >
            View full detail
            <ExternalLink size={11} />
          </button>

          <button
            type="button"
            onClick={() => handleDeleteCampaign(campaign.campaignId)}
            disabled={isDeleting}
            className="inline-flex items-center gap-1 text-xs text-[var(--accent-red)] hover:underline disabled:opacity-50"
          >
            {isDeleting ? (
              <Loader2 size={11} className="animate-spin" />
            ) : (
              <Trash2 size={11} />
            )}
            Delete campaign
          </button>
        </div>
      </div>
    );
  }, [detailCache, detailLoading, selectedLegIds, toggleLegSelection, toggleAllLegsForCampaign, navigate, handleDeleteCampaign, deletingCampaign]);

  const totalOrphanedLegs = orphanedGroups.reduce((sum, g) => sum + g.legs.length, 0);

  return (
    <div className="p-6">
      {/* Uncategorized trades banner */}
      {uncategorizedCount > 0 && !bannerDismissed && (
        <div className="mb-4 flex items-center justify-between rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3">
          <div className="flex items-center gap-3">
            <AlertTriangle size={18} className="text-amber-500 flex-shrink-0" />
            <span className="text-sm text-[var(--text-primary)]">
              You have <span className="font-semibold">{uncategorizedCount}</span> trade
              {uncategorizedCount !== 1 ? 's' : ''} without a strategy.
              Categorize them for better trading insights.
            </span>
          </div>
          <button
            onClick={() => setBannerDismissed(true)}
            className="ml-4 p-1 text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
            aria-label="Dismiss"
          >
            <X size={16} />
          </button>
        </div>
      )}

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

      {/* Bulk edit bar - shown when legs are selected */}
      {hasSelection && (
        <div className="mb-3 flex flex-wrap items-center gap-3 rounded-lg border border-[var(--accent-blue)]/30 bg-[var(--accent-blue)]/5 px-4 py-3">
          <span className="text-sm font-medium text-[var(--text-primary)]">
            {selectedLegIds.size} leg{selectedLegIds.size !== 1 ? 's' : ''} selected
          </span>

          <div className="mx-1 h-5 w-px bg-[var(--border-color)]" />

          {/* Strategy dropdown */}
          <label className="flex items-center gap-2 text-xs text-[var(--text-secondary)]">
            Strategy:
            <select
              value={bulkStrategyId}
              onChange={(e) => setBulkStrategyId(e.target.value)}
              disabled={strategiesLoading || bulkApplying}
              className="h-8 min-w-[180px] rounded-md border border-[var(--border-color)] bg-[var(--bg-primary)] px-2 text-xs text-[var(--text-primary)] focus:border-[var(--accent-blue)] focus:outline-none disabled:opacity-50"
            >
              <option value="">
                {strategiesLoading ? 'Loading...' : '-- Select strategy --'}
              </option>
              {strategies.filter((s) => s.is_active).map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </label>

          {/* Apply button */}
          <button
            type="button"
            onClick={handleBulkApply}
            disabled={!bulkStrategyId || bulkApplying}
            className="inline-flex h-8 items-center gap-1.5 rounded-md bg-[var(--accent-blue)] px-4 text-xs font-medium text-white transition-colors hover:bg-[var(--accent-blue)]/90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {bulkApplying && <Loader2 size={13} className="animate-spin" />}
            Apply
          </button>

          {/* Cancel button */}
          <button
            type="button"
            onClick={handleClearSelection}
            disabled={bulkApplying}
            className="inline-flex h-8 items-center gap-1 rounded-md border border-[var(--border-color)] px-3 text-xs text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-primary)] disabled:opacity-50"
          >
            <X size={13} />
            Cancel
          </button>

          {/* Error message */}
          {bulkError && (
            <span className="text-xs text-[var(--accent-red)]">{bulkError}</span>
          )}
        </div>
      )}

      {/* Success message */}
      {bulkSuccess && !hasSelection && (
        <div className="mb-3 flex items-center gap-2 rounded-lg border border-[var(--accent-green)]/30 bg-[var(--accent-green)]/5 px-4 py-2.5">
          <span className="text-xs text-[var(--accent-green)]">{bulkSuccess}</span>
          <button
            type="button"
            onClick={() => setBulkSuccess(null)}
            className="ml-auto text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
          >
            <X size={13} />
          </button>
        </div>
      )}

      {/* Orphaned Legs Section — shown first */}
      {orphanedGroups.length > 0 && (
        <div className="mb-6">
          <h2 className="mb-3 text-lg font-semibold text-[var(--text-primary)]">
            Orphaned Legs
            <span className="ml-2 text-sm font-normal text-[var(--text-secondary)]">
              {totalOrphanedLegs} leg{totalOrphanedLegs !== 1 ? 's' : ''} without a campaign
            </span>
          </h2>
          <p className="mb-4 text-xs text-[var(--text-secondary)]">
            These legs were preserved when their campaigns were deleted. Assign a strategy to auto-group them into new campaigns.
          </p>

          <div className="space-y-2">
            {orphanedGroups.map((group) => {
              const groupKey = group.symbol;
              const isExpanded = expandedOrphanGroups.has(groupKey);
              const allSelected = group.legs.every((l) => selectedLegIds.has(l.legId));

              return (
                <div
                  key={groupKey}
                  className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)]"
                >
                  {/* Group header */}
                  <button
                    type="button"
                    onClick={() => toggleOrphanGroup(groupKey)}
                    className="flex w-full items-center gap-3 px-4 py-3 text-left"
                  >
                    {isExpanded ? (
                      <ChevronDown size={14} className="text-[var(--text-secondary)]" />
                    ) : (
                      <ChevronRight size={14} className="text-[var(--text-secondary)]" />
                    )}
                    <span className="font-medium text-[var(--text-primary)]">
                      {group.symbol}
                    </span>
                    <span className="text-xs text-[var(--text-secondary)]">
                      {group.legs.length} leg{group.legs.length !== 1 ? 's' : ''}
                    </span>
                  </button>

                  {/* Expanded legs table */}
                  {isExpanded && (
                    <div className="border-t border-[var(--border-color)] px-4 py-3">
                      <table className="w-full text-xs">
                        <thead>
                          <tr className="text-left text-[10px] font-medium uppercase tracking-wider text-[var(--text-secondary)]">
                            <th className="w-8 px-2 py-1.5">
                              <input
                                type="checkbox"
                                checked={allSelected}
                                onChange={() => toggleAllOrphanedLegs(group.legs)}
                                className="h-3 w-3 rounded border-[var(--border-color)] text-[var(--accent-blue)] focus:ring-[var(--accent-blue)]"
                                aria-label="Select all orphaned legs"
                              />
                            </th>
                            <th className="px-3 py-1.5">Type</th>
                            <th className="px-3 py-1.5">Direction</th>
                            <th className="px-3 py-1.5">Side</th>
                            <th className="px-3 py-1.5">Qty</th>
                            <th className="px-3 py-1.5">Price</th>
                            <th className="px-3 py-1.5">Date</th>
                            <th className="px-3 py-1.5">Strategy</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-[var(--border-color)]/50">
                          {group.legs.map((leg) => {
                            const isLegSelected = selectedLegIds.has(leg.legId);
                            return (
                              <tr
                                key={leg.legId}
                                className={`transition-colors ${isLegSelected ? 'bg-[var(--accent-blue)]/5' : ''}`}
                              >
                                <td className="w-8 px-2 py-2">
                                  <input
                                    type="checkbox"
                                    checked={isLegSelected}
                                    onChange={() => toggleLegSelection(leg.legId)}
                                    className="h-3 w-3 rounded border-[var(--border-color)] text-[var(--accent-blue)] focus:ring-[var(--accent-blue)]"
                                    aria-label={`Select orphaned leg ${leg.legId}`}
                                  />
                                </td>
                                <td className="px-3 py-2">
                                  <span className="inline-block rounded px-1.5 py-0.5 text-[10px] font-medium bg-[var(--bg-tertiary)] text-[var(--text-secondary)]">
                                    {leg.legType}
                                  </span>
                                </td>
                                <td className="px-3 py-2">
                                  <span
                                    className={`text-xs font-medium ${
                                      leg.direction === 'long'
                                        ? 'text-[var(--accent-green)]'
                                        : 'text-[var(--accent-red)]'
                                    }`}
                                  >
                                    {leg.direction.toUpperCase()}
                                  </span>
                                </td>
                                <td className="px-3 py-2">
                                  <span
                                    className={`font-medium ${
                                      leg.side === 'buy'
                                        ? 'text-[var(--accent-green)]'
                                        : 'text-[var(--accent-red)]'
                                    }`}
                                  >
                                    {leg.side.toUpperCase()}
                                  </span>
                                </td>
                                <td className="px-3 py-2 text-[var(--text-secondary)]">
                                  {leg.quantity}
                                </td>
                                <td className="px-3 py-2 text-[var(--text-secondary)]">
                                  ${leg.avgPrice.toFixed(2)}
                                </td>
                                <td className="px-3 py-2 text-[var(--text-secondary)]">
                                  {formatLegDate(leg.startedAt)}
                                </td>
                                <td className="px-3 py-2 text-[var(--text-secondary)]">
                                  {leg.strategyName ?? '-'}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* DataTable with column visibility persistence and expandable rows */}
      <DataTable
        tableName="campaigns"
        columns={columns}
        data={filtered}
        loading={loading}
        emptyMessage="No campaigns match your search."
        getRowKey={(campaign) => campaign.campaignId}
        expandedKeys={expandedCampaignIds}
        onExpandChange={handleExpandChange}
        renderExpandedRow={renderExpandedRow}
      />
    </div>
  );
}
