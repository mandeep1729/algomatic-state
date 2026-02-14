import type {
  CampaignSummary,
  CampaignDetail,
  CampaignLeg,
  EvaluationBundle,
  OverallLabel,
} from '../../types';

const mkBundle = (
  overallLabel: OverallLabel,
  dims: EvaluationBundle['dimensions'],
): EvaluationBundle => ({
  bundleId: `b-${Math.random().toString(36).slice(2, 10)}`,
  evalScope: 'campaign',
  overallLabel,
  dimensions: dims,
});

// ---------------------------------------------------------------------------
// Campaign Summaries
// ---------------------------------------------------------------------------

export const MOCK_CAMPAIGN_SUMMARIES: CampaignSummary[] = [
  {
    campaignId: 'c1',
    symbol: 'AAPL',
    direction: 'long',
    status: 'closed',
    openedAt: '2026-02-01T10:15:00-08:00',
    closedAt: '2026-02-06T11:20:00-08:00',
    legsCount: 3,
    maxQty: 150,
    legQuantities: [100, 50, -150],
    overallLabel: 'mixed',
    keyFlags: ['exit_early', 'add_late', 'vol_high'],
    strategies: ['pullback', 'momentum'],
    pnlRealized: 460.0,
  },
  {
    campaignId: 'c2',
    symbol: 'TSLA',
    direction: 'short',
    status: 'closed',
    openedAt: '2026-02-03T09:45:00-08:00',
    closedAt: '2026-02-03T13:05:00-08:00',
    legsCount: 2,
    maxQty: 50,
    legQuantities: [-50, 50],
    overallLabel: 'fragile',
    keyFlags: ['regime_mismatch', 'rushed_trade'],
    strategies: ['mean-reversion', 'gap-fade'],
    pnlRealized: -135.50,
  },
];

// ---------------------------------------------------------------------------
// AAPL Legs
// ---------------------------------------------------------------------------

const legsAAPL: CampaignLeg[] = [
  {
    legId: 'l1',
    campaignId: 'c1',
    legType: 'open',
    side: 'buy',
    quantity: 100,
    avgPrice: 182.1,
    startedAt: '2026-02-01T10:15:00-08:00',
    endedAt: '2026-02-01T10:15:10-08:00',
  },
  {
    legId: 'l2',
    campaignId: 'c1',
    legType: 'add',
    side: 'buy',
    quantity: 50,
    avgPrice: 184.3,
    startedAt: '2026-02-03T11:02:00-08:00',
    endedAt: '2026-02-03T11:02:08-08:00',
  },
  {
    legId: 'l3',
    campaignId: 'c1',
    legType: 'close',
    side: 'sell',
    quantity: 150,
    avgPrice: 186.0,
    startedAt: '2026-02-06T11:20:00-08:00',
    endedAt: '2026-02-06T11:20:05-08:00',
  },
];

// ---------------------------------------------------------------------------
// TSLA Legs
// ---------------------------------------------------------------------------

const legsTSLA: CampaignLeg[] = [
  {
    legId: 'l4',
    campaignId: 'c2',
    legType: 'open',
    side: 'sell',
    quantity: 50,
    avgPrice: 248.5,
    startedAt: '2026-02-03T09:45:00-08:00',
    endedAt: '2026-02-03T09:45:06-08:00',
  },
  {
    legId: 'l5',
    campaignId: 'c2',
    legType: 'close',
    side: 'buy',
    quantity: 50,
    avgPrice: 251.2,
    startedAt: '2026-02-03T13:05:00-08:00',
    endedAt: '2026-02-03T13:05:04-08:00',
  },
];

// ---------------------------------------------------------------------------
// Campaign Details
// ---------------------------------------------------------------------------

export const MOCK_CAMPAIGN_DETAILS: Record<string, CampaignDetail> = {
  c1: {
    campaign: {
      campaignId: 'c1',
      symbol: 'AAPL',
      direction: 'long',
      status: 'closed',
      openedAt: '2026-02-01T10:15:00-08:00',
      closedAt: '2026-02-06T11:20:00-08:00',
      legsCount: 3,
      maxQty: 150,
      pnlRealized: 460,
      costBasisMethod: 'average',
      source: 'broker_synced',
    },
    legs: legsAAPL,
    evaluationCampaign: mkBundle('mixed', [
      {
        dimensionKey: 'regime_fit',
        severity: 'medium',
        label: 'Mixed regime fit',
        explanation:
          'Campaign spanned a volatility expansion period; your strategy tends to be less stable there.',
        visuals: { type: 'risk_path' },
      },
      {
        dimensionKey: 'behavioral',
        severity: 'low',
        label: 'Slight urgency on add',
        explanation:
          'Adds occurred shortly after a prior loss cluster in the same week.',
        visuals: { type: 'behavior_timeline' },
      },
      {
        dimensionKey: 'risk_structure',
        severity: 'info',
        label: 'Risk defined',
        explanation:
          'Stop/invalidations were present (from inputs/notes); sizing stayed within your typical band.',
      },
    ]),
    evaluationByLeg: {
      l1: {
        bundleId: 'b-l1',
        evalScope: 'leg',
        overallLabel: 'aligned',
        dimensions: [
          {
            dimensionKey: 'entry_timing',
            severity: 'low',
            label: 'Entry timing ok',
            explanation:
              'Entry aligned with your stated setup window; not extended versus reference.',
            visuals: { type: 'price_snapshot', anchor: 'entry' },
          },
          {
            dimensionKey: 'strategy_consistency',
            severity: 'info',
            label: 'Consistent with pullback style',
            explanation: 'Matches your typical pullback entry profile.',
          },
        ],
      },
      l2: {
        bundleId: 'b-l2',
        evalScope: 'leg',
        overallLabel: 'mixed',
        dimensions: [
          {
            dimensionKey: 'entry_timing',
            severity: 'medium',
            label: 'Add was late',
            explanation:
              'Add occurred after a large impulse; your adds historically underperform when extended.',
            visuals: { type: 'price_snapshot', anchor: 'add' },
          },
          {
            dimensionKey: 'behavioral',
            severity: 'medium',
            label: 'Rushed add risk',
            explanation:
              'Add timing correlates with urgency patterns in your history (same-day streak behavior).',
          },
        ],
      },
      l3: {
        bundleId: 'b-l3',
        evalScope: 'leg',
        overallLabel: 'aligned',
        dimensions: [
          {
            dimensionKey: 'exit_logic',
            severity: 'low',
            label: 'Exit disciplined',
            explanation:
              'Exit followed your profit-taking style (scale/target).',
            visuals: { type: 'price_snapshot', anchor: 'exit' },
          },
          {
            dimensionKey: 'risk_structure',
            severity: 'info',
            label: 'Exposure reduced cleanly',
            explanation:
              'Close returned position to flat without stop widening.',
          },
        ],
      },
    },
    contextsByLeg: {
      l1: {
        contextId: 'cx1',
        scope: 'leg',
        campaignId: 'c1',
        legId: 'l1',
        contextType: 'entry',
        strategyTags: ['pullback', 'momentum'],
        hypothesis: 'Pullback holds near VWAP and resumes trend.',
        exitIntent: 'scale',
        feelingsThen: { chips: ['calm', 'focused'], intensity: 2 },
        notes: 'Planned to add only if pullback shallow.',
        updatedAt: new Date().toISOString(),
      },
      l2: undefined,
      l3: undefined,
    },
    checksByLeg: {},
  },

  c2: {
    campaign: {
      campaignId: 'c2',
      symbol: 'TSLA',
      direction: 'short',
      status: 'closed',
      openedAt: '2026-02-03T09:45:00-08:00',
      closedAt: '2026-02-03T13:05:00-08:00',
      legsCount: 2,
      maxQty: 50,
      pnlRealized: -135,
      costBasisMethod: 'average',
      source: 'broker_synced',
    },
    legs: legsTSLA,
    evaluationCampaign: mkBundle('fragile', [
      {
        dimensionKey: 'regime_fit',
        severity: 'high',
        label: 'Regime mismatch',
        explanation:
          'Shorted during a momentum-up regime; historical win rate for shorts in this regime is below 30%.',
        visuals: { type: 'risk_path' },
      },
      {
        dimensionKey: 'behavioral',
        severity: 'medium',
        label: 'Rushed trade',
        explanation:
          'Entry came within 15 minutes of market open during a gap-up day — a pattern linked to impulsive entries in your history.',
        visuals: { type: 'behavior_timeline' },
      },
      {
        dimensionKey: 'risk_structure',
        severity: 'medium',
        label: 'Stop too tight',
        explanation:
          'Initial stop was within 0.4 ATR; your typical winning shorts use at least 1.0 ATR.',
      },
    ]),
    evaluationByLeg: {
      l4: {
        bundleId: 'b-l4',
        evalScope: 'leg',
        overallLabel: 'fragile',
        dimensions: [
          {
            dimensionKey: 'entry_timing',
            severity: 'high',
            label: 'Entry in open volatility',
            explanation:
              'Entered during the first 15 minutes of a gap-up session; this window has high reversal noise.',
            visuals: { type: 'price_snapshot', anchor: 'entry' },
          },
          {
            dimensionKey: 'strategy_consistency',
            severity: 'medium',
            label: 'Contradicts stated setup',
            explanation:
              'Your short setup requires failed breakout confirmation — none was present at entry.',
          },
        ],
      },
      l5: {
        bundleId: 'b-l5',
        evalScope: 'leg',
        overallLabel: 'mixed',
        dimensions: [
          {
            dimensionKey: 'exit_logic',
            severity: 'medium',
            label: 'Stopped out — no scale exit',
            explanation:
              'Exit was a hard stop hit, not a planned scale-out; position went from full to flat.',
            visuals: { type: 'price_snapshot', anchor: 'exit' },
          },
          {
            dimensionKey: 'behavioral',
            severity: 'low',
            label: 'Held through adverse move',
            explanation:
              'Price moved 1.2% against within 30 minutes; earlier exit could have reduced loss by ~40%.',
          },
        ],
      },
    },
    contextsByLeg: {
      l4: {
        contextId: 'cx2',
        scope: 'leg',
        campaignId: 'c2',
        legId: 'l4',
        contextType: 'entry',
        strategyTags: ['mean-reversion', 'gap-fade'],
        hypothesis: 'Gap-up is overdone, expecting fade back to VWAP.',
        exitIntent: 'fixed',
        feelingsThen: { chips: ['anxious', 'impulsive'], intensity: 4 },
        notes: 'Felt like I had to get in before it reversed. No confirmation waited for.',
        updatedAt: new Date().toISOString(),
      },
      l5: undefined,
    },
    checksByLeg: {},
  },
};
