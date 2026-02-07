import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import api from '../../api';
import { USE_MOCKS } from '../../mocks/enable';
import { fetchMockCampaignOHLCVData } from '../../mocks/mockApi';
import { fetchCampaignOHLCVData } from '../../api';
import { Timeline } from '../../components/campaigns/Timeline';
import { EvaluationGrid } from '../../components/campaigns/EvaluationGrid';
import { ContextPanel } from '../../components/campaigns/ContextPanel';
import { OverallLabelBadge } from '../../components/campaigns/OverallLabelBadge';
import { CampaignPricePnlChart } from '../../components/campaigns/CampaignPricePnlChart';
import type { LegMarker } from '../../components/campaigns/CampaignPricePnlChart';
import type { CampaignDetail as CampaignDetailType, CampaignLeg, DecisionContext, EvaluationBundle } from '../../types';

/**
 * Compute running (unrealized + realized) PNL for a campaign at each OHLCV timestamp.
 * Tracks net position from legs and marks-to-market against close prices.
 */
function computeCampaignRunningPnl(
  legs: CampaignLeg[],
  direction: 'long' | 'short',
  ohlcvTimestamps: string[],
  closePrices: number[],
): number[] {
  const dirSign = direction === 'long' ? 1 : -1;

  // Build position events from legs sorted by time
  const events = legs
    .map((leg) => ({
      timeMs: new Date(leg.startedAt).getTime(),
      // buy adds to position, sell removes
      deltaQty: leg.side === 'buy' ? leg.quantity : -leg.quantity,
      price: leg.avgPrice,
    }))
    .sort((a, b) => a.timeMs - b.timeMs);

  const pnl: number[] = [];
  let netQty = 0;
  let totalCost = 0; // running cost basis (signed by direction)
  let realizedPnl = 0;
  let eventIdx = 0;

  for (let i = 0; i < ohlcvTimestamps.length; i++) {
    const tsMs = new Date(ohlcvTimestamps[i]).getTime();

    // Process any legs that occurred at or before this timestamp
    while (eventIdx < events.length && events[eventIdx].timeMs <= tsMs) {
      const ev = events[eventIdx];
      if (ev.deltaQty > 0) {
        // Adding to position
        totalCost += ev.price * ev.deltaQty;
        netQty += ev.deltaQty;
      } else {
        // Reducing position — realize PnL on closed portion
        const closingQty = Math.abs(ev.deltaQty);
        const avgCost = netQty > 0 ? totalCost / netQty : ev.price;
        realizedPnl += (ev.price - avgCost) * closingQty * dirSign;
        totalCost -= avgCost * closingQty;
        netQty -= closingQty;
      }
      eventIdx++;
    }

    // Mark-to-market unrealized PnL on remaining position
    const avgCost = netQty > 0 ? totalCost / netQty : 0;
    const unrealizedPnl = netQty > 0
      ? (closePrices[i] - avgCost) * netQty * dirSign
      : 0;

    pnl.push(+(realizedPnl + unrealizedPnl).toFixed(2));
  }

  return pnl;
}

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
    if (!detail) return;
    const { campaign, legs } = detail;
    const symbol = campaign.symbol;
    symbolRef.current = symbol;
    let cancelled = false;

    async function loadChartData() {
      setChartLoading(true);
      setChartError(null);
      try {
        // Fetch OHLCV covering the full campaign date range so all leg
        // markers (OPEN, ADD, CLOSE, etc.) map to distinct chart positions.
        const rangeStartMs = new Date(campaign.openedAt).getTime();
        const rangeEndMs = campaign.closedAt
          ? new Date(campaign.closedAt).getTime()
          : Date.now();

        const ohlcv = USE_MOCKS
          ? await fetchMockCampaignOHLCVData(symbol, rangeStartMs, rangeEndMs)
          : await fetchCampaignOHLCVData(symbol, rangeStartMs, rangeEndMs);
        if (cancelled) return;

        const filteredTs = ohlcv.timestamps;
        const filteredClose = ohlcv.close;

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

  const isCampaignTab = tab === 'campaign';
  const selectedLeg = !isCampaignTab && detail
    ? detail.legs.find((l) => l.legId === tab)
    : undefined;

  // Resolve evaluation bundle for the current tab
  const currentBundle: EvaluationBundle | null = useMemo(() => {
    if (!detail) return null;
    if (isCampaignTab) return detail.evaluationCampaign;
    if (selectedLeg) return detail.evaluationByLeg[selectedLeg.legId] ?? null;
    return null;
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
    } catch {
      // Silently fail -- context is still saved locally in state
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
            return (
              <button
                key={t.key}
                type="button"
                onClick={() => handleTabClick(t.key)}
                className={`rounded-md border px-3 py-1.5 text-xs font-medium transition-colors ${
                  isActive
                    ? 'border-[var(--accent-blue)] bg-[var(--accent-blue)]/10 text-[var(--accent-blue)]'
                    : 'border-[var(--border-color)] text-[var(--text-secondary)] hover:border-[var(--text-secondary)] hover:text-[var(--text-primary)]'
                }`}
              >
                {t.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Content: 2-column layout */}
      <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
        {/* Left column: Evaluation */}
        <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-5">
          <h2 className="mb-4 text-sm font-medium text-[var(--text-primary)]">
            {isCampaignTab
              ? 'Evaluation (Campaign)'
              : `Evaluation (${selectedLeg?.legType.toUpperCase() ?? 'Leg'})`}
          </h2>
          {currentBundle ? (
            <EvaluationGrid bundle={currentBundle} />
          ) : (
            <p className="text-sm text-[var(--text-secondary)]">
              No evaluation data available for this selection.
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
