export default function HelpEvaluations() {
  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="mb-6 text-3xl font-bold">Understanding Evaluations</h1>

      <div className="space-y-6 text-sm leading-relaxed text-[var(--text-secondary)]">
        <section>
          <h2 className="mb-2 text-lg font-medium text-[var(--text-primary)]">How Evaluations Work</h2>
          <p>
            When you submit a trade for evaluation, Trading Buddy runs it through six independent
            evaluators. Each evaluator examines a different dimension of the trade and produces
            findings with evidence and a severity level.
          </p>
        </section>

        <section>
          <h2 className="mb-2 text-lg font-medium text-[var(--text-primary)]">The Six Dimensions</h2>
          <div className="space-y-3">
            {[
              { name: 'Regime Fit', desc: 'Checks whether the trade direction aligns with the current market regime (trending, mean-reverting, volatile, etc.).' },
              { name: 'Entry Timing', desc: 'Evaluates whether the entry timing is appropriate. Flags rushed entries, trades during extreme volatility, and suboptimal windows.' },
              { name: 'Exit Logic', desc: 'Reviews stop loss and profit target placement. Checks R:R ratio against your minimum and validates levels against support/resistance.' },
              { name: 'Risk Positioning', desc: 'Validates position sizing against your max loss per trade, daily loss limits, and open position count.' },
              { name: 'Behavioral', desc: 'Detects patterns like revenge trading, FOMO, overconfidence, and other behavioral signals correlated with poor outcomes.' },
              { name: 'Strategy Consistency', desc: 'Compares the trade against your declared strategies. Checks direction, timeframe, entry/exit criteria, and risk parameters.' },
            ].map((dim) => (
              <div key={dim.name} className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
                <h3 className="text-sm font-semibold text-[var(--text-primary)]">{dim.name}</h3>
                <p className="mt-1 text-xs">{dim.desc}</p>
              </div>
            ))}
          </div>
        </section>

        <section>
          <h2 className="mb-2 text-lg font-medium text-[var(--text-primary)]">Scores</h2>
          <p>
            The overall score (0-100) reflects the aggregate quality of the trade setup. It is
            computed by starting at 100 and deducting points for each finding based on severity:
          </p>
          <ul className="mt-2 ml-4 list-disc space-y-1 text-xs">
            <li><strong>Info:</strong> No deduction (observation only)</li>
            <li><strong>Warning:</strong> Small deduction (-5 to -10)</li>
            <li><strong>Critical:</strong> Moderate deduction (-15 to -25)</li>
            <li><strong>Blocker:</strong> Large deduction (-25 to -40)</li>
          </ul>
        </section>

        <section>
          <h2 className="mb-2 text-lg font-medium text-[var(--text-primary)]">Evidence</h2>
          <p>
            Each finding includes evidence — specific metrics with values, thresholds, and
            comparisons. This lets you see exactly why something was flagged, not just that
            it was flagged.
          </p>
          <div className="mt-2 rounded border border-[var(--border-color)] bg-[var(--bg-primary)] p-3 font-mono text-xs">
            position_risk_pct: 3.5% &gt; 2.0% (threshold)
          </div>
          <p className="mt-2">
            This example shows that your position risk of 3.5% exceeds your configured maximum
            of 2.0%.
          </p>
        </section>
      </div>
    </div>
  );
}
