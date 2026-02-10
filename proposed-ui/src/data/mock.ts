import { CampaignDetail, CampaignSummary, EvaluationBundle, Leg, OverallLabel } from "../types/domain";

const mkBundle = (overallLabel: OverallLabel, dims: EvaluationBundle["dimensions"]): EvaluationBundle => ({
  bundleId: crypto.randomUUID(),
  evalScope: "campaign",
  overallLabel,
  dimensions: dims,
});

export const campaignSummaries: CampaignSummary[] = [
  {
    campaignId: "c1",
    symbol: "AAPL",
    direction: "long",
    status: "closed",
    openedAt: "2026-02-01T10:15:00-08:00",
    closedAt: "2026-02-06T11:20:00-08:00",
    legsCount: 3,
    maxQty: 150,
    overallLabel: "mixed",
    keyFlags: ["exit_early", "add_late", "vol_high"],
  },
  {
    campaignId: "c2",
    symbol: "TSLA",
    direction: "short",
    status: "closed",
    openedAt: "2026-02-03T09:45:00-08:00",
    closedAt: "2026-02-03T13:05:00-08:00",
    legsCount: 2,
    maxQty: 50,
    overallLabel: "fragile",
    keyFlags: ["regime_mismatch", "rushed_trade"],
  },
];

const legsAAPL: Leg[] = [
  { legId: "l1", campaignId: "c1", legType: "open", side: "buy", quantity: 100, avgPrice: 182.1, startedAt: "2026-02-01T10:15:00-08:00", endedAt: "2026-02-01T10:15:10-08:00" },
  { legId: "l2", campaignId: "c1", legType: "add",  side: "buy", quantity: 50,  avgPrice: 184.3, startedAt: "2026-02-03T11:02:00-08:00", endedAt: "2026-02-03T11:02:08-08:00" },
  { legId: "l3", campaignId: "c1", legType: "close",side: "sell",quantity: 150, avgPrice: 186.0, startedAt: "2026-02-06T11:20:00-08:00", endedAt: "2026-02-06T11:20:05-08:00" },
];

export const campaignDetailById: Record<string, CampaignDetail> = {
  c1: {
    campaign: {
      campaignId: "c1",
      symbol: "AAPL",
      direction: "long",
      status: "closed",
      openedAt: "2026-02-01T10:15:00-08:00",
      closedAt: "2026-02-06T11:20:00-08:00",
      legsCount: 3,
      maxQty: 150,
      pnlRealized: 460,
      costBasisMethod: "average",
      source: "broker_synced",
    },
    legs: legsAAPL,
    evaluationCampaign: mkBundle("mixed", [
      { dimensionKey: "regime_fit", severity: "medium", label: "Mixed regime fit", explanation: "Campaign spanned a volatility expansion period; your strategy tends to be less stable there.", visuals: { type: "risk_path" } },
      { dimensionKey: "behavioral", severity: "low", label: "Slight urgency on add", explanation: "Adds occurred shortly after a prior loss cluster in the same week.", visuals: { type: "behavior_timeline" } },
      { dimensionKey: "risk_structure", severity: "info", label: "Risk defined", explanation: "Stop/invalidations were present (from inputs/notes); sizing stayed within your typical band." },
    ]),
    evaluationByLeg: {
      l1: { bundleId: "b-l1", evalScope: "leg", overallLabel: "aligned", dimensions: [
        { dimensionKey: "entry_timing", severity: "low", label: "Entry timing ok", explanation: "Entry aligned with your stated setup window; not extended versus reference." , visuals: { type: "price_snapshot", anchor: "entry" }},
        { dimensionKey: "strategy_consistency", severity: "info", label: "Consistent with pullback style", explanation: "Matches your typical pullback entry profile." },
      ]},
      l2: { bundleId: "b-l2", evalScope: "leg", overallLabel: "mixed", dimensions: [
        { dimensionKey: "entry_timing", severity: "medium", label: "Add was late", explanation: "Add occurred after a large impulse; your adds historically underperform when extended.", visuals: { type: "price_snapshot", anchor: "add" } },
        { dimensionKey: "behavioral", severity: "medium", label: "Rushed add risk", explanation: "Add timing correlates with urgency patterns in your history (same-day streak behavior)." },
      ]},
      l3: { bundleId: "b-l3", evalScope: "leg", overallLabel: "aligned", dimensions: [
        { dimensionKey: "exit_logic", severity: "low", label: "Exit disciplined", explanation: "Exit followed your profit-taking style (scale/target).", visuals: { type: "price_snapshot", anchor: "exit" } },
        { dimensionKey: "risk_structure", severity: "info", label: "Exposure reduced cleanly", explanation: "Close returned position to flat without stop widening." },
      ]},
    },
    contextsByLeg: {
      l1: {
        contextId: "cx1",
        scope: "leg",
        campaignId: "c1",
        legId: "l1",
        contextType: "entry",
        strategyTags: ["pullback", "momentum"],
        hypothesis: "Pullback holds near VWAP and resumes trend.",
        exitIntent: "scale",
        feelingsThen: { chips: ["calm", "focused"], intensity: 2 },
        notes: "Planned to add only if pullback shallow.",
        updatedAt: new Date().toISOString(),
      },
      l2: undefined,
      l3: undefined,
    },
  },
};
