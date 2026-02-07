import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { fetchCampaignDetail, saveDecisionContext } from '../../mocks/mockApi';
import { Timeline } from '../../components/campaigns/Timeline';
import { EvaluationGrid } from '../../components/campaigns/EvaluationGrid';
import { ContextPanel } from '../../components/campaigns/ContextPanel';
import { OverallLabelBadge } from '../../components/campaigns/OverallLabelBadge';
import type { CampaignDetail as CampaignDetailType, DecisionContext, EvaluationBundle } from '../../types';

type TabKey = 'campaign' | string;

export default function CampaignDetail() {
  const { campaignId } = useParams<{ campaignId: string }>();
  const [detail, setDetail] = useState<CampaignDetailType | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<TabKey>('campaign');
  const [activeLegIndex, setActiveLegIndex] = useState(0);
  const [contextsByLeg, setContextsByLeg] = useState<Record<string, DecisionContext | undefined>>({});

  useEffect(() => {
    if (!campaignId) return;
    let cancelled = false;

    async function load() {
      setLoading(true);
      try {
        const data = await fetchCampaignDetail(campaignId!);
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
      await saveDecisionContext(ctx);
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
        <div className="mt-2 text-xs text-[var(--text-secondary)]">
          Opened {new Date(detail.campaign.openedAt).toLocaleString()}
          {detail.campaign.closedAt
            ? ` \u00B7 Closed ${new Date(detail.campaign.closedAt).toLocaleString()}`
            : ' \u00B7 Open'}
          {' \u00B7 '}Source: {detail.campaign.source.replace(/_/g, ' ')}
          {' \u00B7 '}Cost basis: {detail.campaign.costBasisMethod}
          {detail.campaign.pnlRealized != null && (
            <>
              {' \u00B7 '}
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

        {/* Timeline */}
        <div className="mt-4">
          <Timeline
            legs={detail.legs}
            activeIndex={activeLegIndex}
            onSelect={handleTimelineSelect}
          />
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
