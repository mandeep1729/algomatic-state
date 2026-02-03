export default function HelpWhyFlags() {
  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="mb-6 text-3xl font-bold">Why We Flag Trades</h1>

      <div className="space-y-6 text-sm leading-relaxed text-[var(--text-secondary)]">
        <p>
          A flagged trade isn't necessarily a bad trade. It's a trade where the system detected
          something that warrants your attention before executing.
        </p>

        <section>
          <h2 className="mb-2 text-lg font-medium text-[var(--text-primary)]">The Purpose of Flags</h2>
          <p>
            Flags exist to slow you down, not to stop you. The goal is to ensure you've
            considered the risks before committing capital. A trade with a flag can still
            be the right trade — but only if you've acknowledged what was flagged and
            decided to proceed deliberately.
          </p>
        </section>

        <section>
          <h2 className="mb-3 text-lg font-medium text-[var(--text-primary)]">Severity Levels Explained</h2>
          <div className="space-y-3">
            <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
              <div className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 rounded-full bg-[var(--accent-blue)]" />
                <h3 className="text-sm font-semibold text-[var(--text-primary)]">Info</h3>
              </div>
              <p className="mt-1 text-xs">
                An observation. No action required. Example: "Current regime is neutral" — not
                a problem, just context for your awareness.
              </p>
            </div>

            <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
              <div className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 rounded-full bg-[var(--accent-yellow)]" />
                <h3 className="text-sm font-semibold text-[var(--text-primary)]">Warning</h3>
              </div>
              <p className="mt-1 text-xs">
                Worth reviewing before executing. Example: "R:R ratio of 1.2 is below your
                minimum of 1.5" — the trade may still work, but you're accepting less reward
                for the risk.
              </p>
            </div>

            <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
              <div className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 rounded-full bg-[var(--accent-red)]" />
                <h3 className="text-sm font-semibold text-[var(--text-primary)]">Critical</h3>
              </div>
              <p className="mt-1 text-xs">
                Significant concern. Reconsider. Example: "Position risk of 4% exceeds your
                2% maximum" — taking this trade as-is violates your own risk rules.
              </p>
            </div>

            <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
              <div className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 rounded-full bg-[var(--accent-red)]" />
                <h3 className="text-sm font-semibold text-[var(--text-primary)]">Blocker</h3>
              </div>
              <p className="mt-1 text-xs">
                Do not take this trade as-is. Example: "No stop loss defined" — proceeding
                without a stop loss exposes you to unlimited downside risk.
              </p>
            </div>
          </div>
        </section>

        <section>
          <h2 className="mb-2 text-lg font-medium text-[var(--text-primary)]">Common Reasons for Flags</h2>
          <ul className="ml-4 list-disc space-y-1 text-xs">
            <li>Missing or poorly-placed stop loss</li>
            <li>Position size exceeding risk limits</li>
            <li>Trading against the prevailing market regime</li>
            <li>Risk:reward ratio below your declared minimum</li>
            <li>Behavioral pattern detected (revenge, FOMO, etc.)</li>
            <li>Trade doesn't match any declared strategy</li>
            <li>Entry during first 15 minutes of market open</li>
            <li>Entry during extreme volatility conditions</li>
          </ul>
        </section>

        <section>
          <h2 className="mb-2 text-lg font-medium text-[var(--text-primary)]">What To Do With a Flagged Trade</h2>
          <ol className="ml-4 list-decimal space-y-1 text-xs">
            <li>Read each finding and its evidence carefully</li>
            <li>Determine if the flag represents a genuine risk you hadn't considered</li>
            <li>Adjust the trade parameters if needed (move stop, reduce size, etc.)</li>
            <li>If you proceed anyway, note why in your journal — track whether flagged trades have different outcomes</li>
          </ol>
        </section>
      </div>
    </div>
  );
}
