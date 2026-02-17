import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import api from '../../api';
import { USE_MOCKS } from '../../mocks/enable';
import { fetchMockCampaignOHLCVData } from '../../mocks/mockApi';
import { fetchCampaignOHLCVData } from '../../api';
import { Timeline } from '../../components/campaigns/Timeline';
import { ChecksSummary } from '../../components/campaigns/ChecksSummary';
import { ContextPanel } from '../../components/campaigns/ContextPanel';
import { OverallLabelBadge } from '../../components/campaigns/OverallLabelBadge';
import { CampaignPricePnlChart } from '../../components/campaigns/CampaignPricePnlChart';
import type { LegMarker } from '../../components/campaigns/CampaignPricePnlChart';
import type { CampaignDetail as CampaignDetailType, CampaignCheck, DecisionContext } from '../../types';
import { computeCampaignRunningPnl } from '../../utils/campaignPnl';

type TabKey = 'campaign' | string;

export default function CampaignDetail() {
  const { campaignId } = useParams<{ campaignId: string }>();
  const [detail, setDetail] = useState<CampaignDetailType | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<TabKey>('campaign');
  const [activeLegIndex, setActiveLegIndex] = useState(0);
  const [contextsByLeg, setContextsByLeg] = useState<Record<string, DecisionContext | undefined>>({});

  // Chart data state
  const [priceTimestamps, setPriceTimestamps] = useState<string[]>([]);
  const [closePrices, setClosePrices] = useState<number[]>([]);
  const [runningPnl, setRunningPnl] = useState<number[]>([]);
  const [chartLegMarkers, setChartLegMarkers] = useState<LegMarker[]>([]);
  const [chartLoading, setChartLoading] = useState(false);
  const [chartError, setChartError] = useState<string | null>(null);
  const symbolRef = useRef<string | null>(null);

  useEffect(() => {
    if (!campaignId) return;
    let cancelled = false;

    async function load() {
      setLoading(true);
      try {
        const data = await api.fetchCampaignDetail(campaignId!);
        if (!cancelled) {
          setDetail(data);
          setContextsByLeg(data.contextsByLeg ?? {});
          setActiveLegIndex(0);
          setTab('campaign');
        }
      } catch {
        // detail stays null, will show "not found" state
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => { cancelled = true; };
  }, [campaignId]);

  // Fetch chart data (price + PnL) when campaign detail is loaded
  useEffect(() => {
    if (!detail || detail.legs.length === 0) return;
    const { campaign, legs } = detail;
    const symbol = campaign.symbol;
    symbolRef.current = symbol;
    let cancelled = false;

    async function loadChartData() {
      setChartLoading(true);
      setChartError(null);
      try {
        // Determine t1 (first leg) and t2 (last leg) timestamps
        const legTimesMs = legs.map((l) => new Date(l.startedAt).getTime());
        const t1Ms = Math.min(...legTimesMs);
        const t2Ms = Math.max(...legTimesMs);
        const spanMs = t2Ms - t1Ms;

        // Fetch with extra padding so we have bars for the 5% buffer.
        // Use 15% padding on the fetch to ensure we have enough data.
        const fetchPadMs = Math.max(spanMs * 0.15, 3600_000); // at least 1h
        const fetchStartMs = t1Ms - fetchPadMs;
        const fetchEndMs = legs.length === 1
          ? Date.now() // single leg: fetch up to now
          : t2Ms + fetchPadMs;

        const ohlcv = USE_MOCKS
          ? await fetchMockCampaignOHLCVData(symbol, fetchStartMs, fetchEndMs)
          : await fetchCampaignOHLCVData(symbol, fetchStartMs, fetchEndMs);
        if (cancelled) return;

        // Find tick indices closest to t1 and t2
        const allTs = ohlcv.timestamps;
        const allClose = ohlcv.close;

        const findClosestIdx = (targetMs: number) => {
          let bestIdx = 0;
          let bestDist = Infinity;
          for (let i = 0; i < allTs.length; i++) {
            const dist = Math.abs(new Date(allTs[i]).getTime() - targetMs);
            if (dist < bestDist) { bestDist = dist; bestIdx = i; }
          }
          return bestIdx;
        };

        const t1Idx = findClosestIdx(t1Ms);
        const t2Idx = findClosestIdx(t2Ms);
        const tickSpan = t2Idx - t1Idx;
        const buffer = Math.max(Math.round(tickSpan * 0.05), 1);

        const windowStart = Math.max(0, t1Idx - buffer);
        // Single leg: show all available data after t1
        const windowEnd = legs.length === 1
          ? allTs.length - 1
          : Math.min(allTs.length - 1, t2Idx + buffer);

        const filteredTs = allTs.slice(windowStart, windowEnd + 1);
        const filteredClose = allClose.slice(windowStart, windowEnd + 1);

        setPriceTimestamps(filteredTs);
        setClosePrices(filteredClose);

        // Compute campaign-specific running PNL from legs
        const pnl = computeCampaignRunningPnl(
          legs,
          campaign.direction,
          filteredTs,
          filteredClose,
        );
        setRunningPnl(pnl);

        // Build leg markers for the chart
        const markers: LegMarker[] = legs.map((leg) => {
          // Find closest price for this leg's timestamp
          const legMs = new Date(leg.startedAt).getTime();
          let closestPrice = leg.avgPrice;
          let bestDist = Infinity;
          for (let i = 0; i < filteredTs.length; i++) {
            const dist = Math.abs(new Date(filteredTs[i]).getTime() - legMs);
            if (dist < bestDist) { bestDist = dist; closestPrice = filteredClose[i]; }
          }

          const isEntry = leg.legType === 'open' || leg.legType === 'add';
          return {
            timestamp: leg.startedAt,
            price: closestPrice,
            label: `${leg.legType.toUpperCase()} @ $${leg.avgPrice.toFixed(2)}`,
            type: isEntry ? 'entry' : 'close',
          } as LegMarker;
        });
        setChartLegMarkers(markers);
      } catch (err) {
        console.error('[CampaignDetail] Chart data load failed:', err);
        setChartError(err instanceof Error ? err.message : 'Failed to load chart data');
        setPriceTimestamps([]);
        setClosePrices([]);
        setRunningPnl([]);
        setChartLegMarkers([]);
      } finally {
        if (!cancelled) setChartLoading(false);
      }
    }

    loadChartData();
    return () => { cancelled = true; };
  }, [detail]);

  // Build tab list from campaign data
  const tabs = useMemo(() => {
    if (!detail) return [];
    return [
      { key: 'campaign' as TabKey, label: 'Campaign Summary' },
      ...detail.legs.map((leg, idx) => ({
        key: leg.legId as TabKey,
        label: `L${idx + 1}: ${leg.legType}`,
      })),
    ];
  }, [detail]);

  // Count critical check failures per leg for badge display
  const CRITICAL_SEVERITIES = new Set(['critical']);
  const criticalCountByLeg = useMemo(() => {
    if (!detail) return {} as Record<string, number>;
    const checksByLeg = detail.checksByLeg ?? {};
    const counts: Record<string, number> = {};
    for (const leg of detail.legs) {
      const checks = checksByLeg[leg.legId] ?? [];
      const criticalCount = checks.filter(
        (c) => CRITICAL_SEVERITIES.has(c.severity) && !c.passed,
      ).length;
      if (criticalCount > 0) {
        counts[leg.legId] = criticalCount;
      }
    }
    return counts;
  }, [detail]);

  const isCampaignTab = tab === 'campaign';
  const selectedLeg = !isCampaignTab && detail
    ? detail.legs.find((l) => l.legId === tab)
    : undefined;

  // Resolve checks for the current tab
  const currentChecks: CampaignCheck[] = useMemo(() => {
    if (!detail) return [];
    const checksByLeg = detail.checksByLeg ?? {};
    if (isCampaignTab) {
      // Flatten all checks from all legs
      return Object.values(checksByLeg).flat();
    }
    if (selectedLeg) {
      return checksByLeg[selectedLeg.legId] ?? [];
    }
    return [];
  }, [detail, isCampaignTab, selectedLeg]);

  // Determine context type based on leg type
  const contextType: DecisionContext['contextType'] = useMemo(() => {
    if (isCampaignTab) return 'post_trade_reflection';
    if (!selectedLeg) return 'entry';
    switch (selectedLeg.legType) {
      case 'close': return 'exit';
      case 'reduce': return 'reduce';
      case 'add': return 'add';
      default: return 'entry';
    }
  }, [isCampaignTab, selectedLeg]);

  // Handle timeline dot click -> sync tab
  const handleTimelineSelect = useCallback((index: number) => {
    if (!detail) return;
    setActiveLegIndex(index);
    const leg = detail.legs[index];
    if (leg) setTab(leg.legId);
  }, [detail]);

  // Handle tab click -> sync timeline
  const handleTabClick = useCallback((key: TabKey) => {
    setTab(key);
    if (key === 'campaign') return;
    if (!detail) return;
    const idx = detail.legs.findIndex((l) => l.legId === key);
    if (idx >= 0) setActiveLegIndex(idx);
  }, [detail]);

  // Autosave handler for context panel
  const handleAutosave = useCallback(async (ctx: DecisionContext) => {
    setContextsByLeg((prev) => ({ ...prev, [ctx.legId ?? 'campaign']: ctx }));
    try {
      await api.saveDecisionContext(ctx);
    } catch (err) {
      // Log the error but don't rethrow -- the ContextPanel will show feedback
      console.error('[CampaignDetail] Failed to save context:', err);
      throw err; // Re-throw so ContextPanel can handle it
    }
  }, []);

  if (loading) {
    return (
      <div className="p-6 text-[var(--text-secondary)]">Loading...</div>
    );
  }

  if (!detail) {
    return (
      <div className="p-6">
        <Link
          to="/app/campaigns"
          className="mb-4 inline-block text-sm text-[var(--accent-blue)] hover:underline"
        >
          &larr; All campaigns
        </Link>
        <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-8 text-center text-sm text-[var(--text-secondary)]">
          Campaign not found.
        </div>
      </div>
    );
  }

  const contextKey = selectedLeg?.legId ?? 'campaign';

  return (
    <div className="p-6">
      {/* Back link */}
      <Link
        to="/app/campaigns"
        className="mb-4 inline-block text-sm text-[var(--accent-blue)] hover:underline"
      >
        &larr; All campaigns
      </Link>

      {/* Header card */}
      <div className="mb-6 rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-5">
        {/* Title row */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-semibold">
              {detail.campaign.symbol}
            </h1>
            <span
              className={`text-sm font-medium ${
                detail.campaign.direction === 'long'
                  ? 'text-[var(--accent-green)]'
                  : 'text-[var(--accent-red)]'
              }`}
            >
              {detail.campaign.direction.toUpperCase()}
            </span>
            <span className="text-sm text-[var(--text-secondary)]">
              {detail.campaign.legsCount} leg{detail.campaign.legsCount !== 1 ? 's' : ''}
            </span>
          </div>
          <OverallLabelBadge label={detail.evaluationCampaign.overallLabel} />
        </div>

        {/* Meta row */}
        <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-[var(--text-secondary)]">
          <span>Source: {detail.campaign.source.replace(/_/g, ' ')}</span>
          <span className="text-[var(--border-color)]">|</span>
          <span>Cost basis: {detail.campaign.costBasisMethod}</span>
          {detail.campaign.pnlRealized != null && (
            <>
              <span className="text-[var(--border-color)]">|</span>
              <span
                className={`font-mono font-medium ${
                  detail.campaign.pnlRealized >= 0
                    ? 'text-[var(--accent-green)]'
                    : 'text-[var(--accent-red)]'
                }`}
              >
                PnL: {detail.campaign.pnlRealized >= 0 ? '+' : ''}
                ${detail.campaign.pnlRealized.toFixed(2)}
              </span>
            </>
          )}
        </div>

        {/* Timeline + Chart side-by-side */}
        <div className="mt-4 flex items-start gap-4">
          {/* Left: Timeline (horizontal leg dots) */}
          <div className="min-w-0 flex-1 pt-1">
            <Timeline
              legs={detail.legs}
              activeIndex={activeLegIndex}
              onSelect={handleTimelineSelect}
            />
          </div>

          {/* Right: Price + PnL chart (60% of panel) */}
          <div className="w-[60%] shrink-0">
            {chartLoading ? (
              <div className="flex h-[180px] items-center justify-center text-xs text-[var(--text-secondary)]">
                Loading chart...
              </div>
            ) : chartError ? (
              <div className="flex h-[180px] items-center justify-center text-xs text-[var(--accent-red)]">
                {chartError}
              </div>
            ) : closePrices.length > 0 ? (
              <CampaignPricePnlChart
                priceTimestamps={priceTimestamps}
                closePrices={closePrices}
                pnlTimestamps={priceTimestamps}
                cumulativePnl={runningPnl}
                legMarkers={chartLegMarkers}
                height={180}
              />
            ) : (
              <div className="flex h-[180px] items-center justify-center text-xs text-[var(--text-secondary)]">
                No price data available
              </div>
            )}
          </div>
        </div>

        {/* Tabs */}
        <div className="mt-4 flex flex-wrap gap-2 border-t border-[var(--border-color)] pt-4">
          {tabs.map((t) => {
            const isActive = tab === t.key;
            const criticalCount = criticalCountByLeg[t.key] ?? 0;
            return (
              <button
                key={t.key}
                type="button"
                onClick={() => handleTabClick(t.key)}
                className={`relative rounded-md border px-3 py-1.5 text-xs font-medium transition-colors ${
                  isActive
                    ? 'border-[var(--accent-blue)] bg-[var(--accent-blue)]/10 text-[var(--accent-blue)]'
                    : 'border-[var(--border-color)] text-[var(--text-secondary)] hover:border-[var(--text-secondary)] hover:text-[var(--text-primary)]'
                }`}
              >
                {t.label}
                {criticalCount > 0 && (
                  <span className="absolute -right-1.5 -top-1.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-[var(--accent-red)] px-1 text-[10px] font-bold leading-none text-white">
                    {criticalCount}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* Content: 2-column layout */}
      <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
        {/* Left column: Checks */}
        <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-5">
          <h2 className="mb-4 text-sm font-medium text-[var(--text-primary)]">
            {isCampaignTab
              ? 'Checks (Campaign)'
              : `Checks (${selectedLeg?.legType.toUpperCase() ?? 'Leg'})`}
          </h2>
          {isCampaignTab ? (
            (() => {
              const checksByLeg = detail.checksByLeg ?? {};
              const legsWithChecks = detail.legs.filter(
                (leg) => (checksByLeg[leg.legId] ?? []).length > 0,
              );
              if (legsWithChecks.length === 0) {
                return (
                  <p className="text-sm text-[var(--text-secondary)]">
                    No checks available for this campaign.
                  </p>
                );
              }
              return (
                <div className="grid gap-6">
                  {legsWithChecks.map((leg) => {
                    const legIndex = detail.legs.indexOf(leg);
                    const label = `L${legIndex + 1}: ${leg.legType}`;
                    return (
                      <ChecksSummary
                        key={leg.legId}
                        checks={checksByLeg[leg.legId]}
                        legLabel={label}
                        showSummary={false}
                      />
                    );
                  })}
                </div>
              );
            })()
          ) : currentChecks.length > 0 ? (
            <ChecksSummary checks={currentChecks} />
          ) : (
            <p className="text-sm text-[var(--text-secondary)]">
              No checks available for this selection.
            </p>
          )}
        </div>

        {/* Right column: Context Panel */}
        <ContextPanel
          title={
            isCampaignTab
              ? 'Context (Campaign-level)'
              : 'Context (This decision point)'
          }
          scope={isCampaignTab ? 'campaign' : 'leg'}
          contextType={contextType}
          campaignId={detail.campaign.campaignId}
          legId={selectedLeg?.legId}
          initial={contextsByLeg[contextKey]}
          onAutosave={handleAutosave}
        />
      </div>
    </div>
  );
}
