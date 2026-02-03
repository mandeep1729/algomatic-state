const DIMENSIONS = [
  {
    name: 'Regime Fit',
    desc: 'Is the current market regime favorable for this trade direction? Trading against the regime is one of the most common causes of losses.',
    examples: ['Going long in a downtrend', 'Trading in choppy/consolidation when your strategy requires trend', 'Ignoring volatility regime shifts'],
  },
  {
    name: 'Entry Timing',
    desc: 'Is the entry well-timed given recent price action? Rushed entries and poor timing account for a large share of unnecessary losses.',
    examples: ['Entering in the first 15 minutes of market open', 'Chasing a move that already happened', 'Entering without waiting for confirmation'],
  },
  {
    name: 'Exit Logic',
    desc: 'Are your stop loss and profit target well-placed? Proper exit planning is often more important than entry selection.',
    examples: ['Stop loss too tight (noise will trigger it)', 'Profit target beyond next major resistance', 'Risk:reward ratio below your minimum threshold'],
  },
  {
    name: 'Risk Positioning',
    desc: 'Is the position sized correctly relative to your account and risk rules? Oversizing is the fastest path to account blowup.',
    examples: ['Position exceeds max loss per trade limit', 'No stop loss defined', 'Already at maximum open positions'],
  },
  {
    name: 'Behavioral Signals',
    desc: 'Are there signs of emotional or impulsive decision-making? These patterns recur across traders and are predictive of poor outcomes.',
    examples: ['Trading to recover a loss (revenge trade)', 'FOMO-driven entry', 'Overconfidence after a winning streak'],
  },
  {
    name: 'Strategy Consistency',
    desc: 'Does this trade match your declared strategy? Deviating from your own rules is one of the strongest indicators of a bad trade.',
    examples: ['Trade doesn\'t match any active strategy', 'Timeframe mismatch', 'Entry criteria not met per your own definition'],
  },
];

export default function WhatWeEvaluate() {
  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="mb-4 text-3xl font-bold">What We Evaluate</h1>
      <p className="mb-10 text-sm text-[var(--text-secondary)]">
        Every trade is evaluated across six dimensions. Each dimension produces findings
        with a severity level: info, warning, critical, or blocker.
      </p>

      <div className="space-y-6">
        {DIMENSIONS.map((dim) => (
          <div key={dim.name} className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-5">
            <h2 className="text-lg font-medium">{dim.name}</h2>
            <p className="mt-2 text-sm text-[var(--text-secondary)]">{dim.desc}</p>
            <div className="mt-3">
              <div className="mb-1 text-[10px] font-medium uppercase tracking-wider text-[var(--text-secondary)]">
                Common flags
              </div>
              <ul className="space-y-1">
                {dim.examples.map((ex) => (
                  <li key={ex} className="flex items-start gap-2 text-xs text-[var(--text-secondary)]">
                    <span className="mt-0.5 text-[var(--accent-yellow)]">&#9679;</span>
                    {ex}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-10 rounded-lg border border-[var(--accent-blue)]/30 bg-[var(--accent-blue)]/5 p-5">
        <h3 className="text-sm font-semibold">Severity Levels</h3>
        <div className="mt-3 space-y-2 text-xs">
          <div className="flex gap-3"><span className="w-16 font-medium text-[var(--text-secondary)]">Info</span> <span>Observation — no action needed.</span></div>
          <div className="flex gap-3"><span className="w-16 font-medium text-[var(--accent-yellow)]">Warning</span> <span>Worth reviewing before executing.</span></div>
          <div className="flex gap-3"><span className="w-16 font-medium text-[var(--accent-red)]">Critical</span> <span>Significant concern — reconsider this trade.</span></div>
          <div className="flex gap-3"><span className="w-16 font-medium text-[var(--accent-red)]">Blocker</span> <span>Do not take this trade as-is.</span></div>
        </div>
      </div>
    </div>
  );
}
