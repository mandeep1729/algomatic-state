export default function HelpBehavioralSignals() {
  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="mb-6 text-3xl font-bold">Behavioral Signals</h1>

      <div className="space-y-6 text-sm leading-relaxed text-[var(--text-secondary)]">
        <p>
          Behavioral signals are patterns detected in your trading that correlate with poor
          outcomes. They're not about individual trades being "right" or "wrong" — they're about
          repeated behaviors that erode performance over time.
        </p>

        <section>
          <h2 className="mb-3 text-lg font-medium text-[var(--text-primary)]">Emotional Signals</h2>
          <div className="space-y-2">
            {[
              { name: 'Revenge Trade', desc: 'Trading to recover a previous loss. Often leads to increased position sizing, lowered standards, and compounding losses.' },
              { name: 'FOMO', desc: 'Fear of missing out driving entries. Typically results in chasing moves that have already played out, with poor risk placement.' },
              { name: 'Overconfidence', desc: 'Excessive certainty after wins leading to oversizing or skipping risk checks. The most dangerous state for a trader.' },
              { name: 'Fear Exit', desc: 'Exiting early due to fear rather than plan. Cuts winners short and damages overall expectancy.' },
            ].map((s) => (
              <SignalCard key={s.name} name={s.name} desc={s.desc} category="emotional" />
            ))}
          </div>
        </section>

        <section>
          <h2 className="mb-3 text-lg font-medium text-[var(--text-primary)]">Process Signals</h2>
          <div className="space-y-2">
            {[
              { name: 'Rushed Entry', desc: 'Entering without completing a pre-trade checklist. Often happens at market open or during fast-moving markets.' },
              { name: 'Strategy Mismatch', desc: 'Trade doesn\'t match any declared strategy. Improvised trades consistently underperform systematic ones.' },
            ].map((s) => (
              <SignalCard key={s.name} name={s.name} desc={s.desc} category="process" />
            ))}
          </div>
        </section>

        <section>
          <h2 className="mb-3 text-lg font-medium text-[var(--text-primary)]">Risk Signals</h2>
          <div className="space-y-2">
            {[
              { name: 'No Stop Loss', desc: 'Placing a trade without a defined stop loss. This is the single most dangerous risk signal.' },
              { name: 'Oversized Position', desc: 'Position size exceeds your maximum loss per trade limit. Even one oversized loss can wipe out weeks of gains.' },
            ].map((s) => (
              <SignalCard key={s.name} name={s.name} desc={s.desc} category="risk" />
            ))}
          </div>
        </section>

        <section>
          <h2 className="mb-3 text-lg font-medium text-[var(--text-primary)]">Timing Signals</h2>
          <div className="space-y-2">
            {[
              { name: 'Poor Timing', desc: 'Entry at a suboptimal time based on recent price action or support/resistance levels.' },
              { name: 'Open Window', desc: 'Trading in the first 15 minutes of market open, when volatility is highest and price discovery is still happening.' },
              { name: 'Extreme Volatility', desc: 'Trading during extreme volatility conditions where normal patterns break down.' },
            ].map((s) => (
              <SignalCard key={s.name} name={s.name} desc={s.desc} category="timing" />
            ))}
          </div>
        </section>

        <section>
          <h2 className="mb-2 text-lg font-medium text-[var(--text-primary)]">Using Behavioral Insights</h2>
          <p>
            The Insights page tracks your behavioral signals over time. The most impactful thing
            you can do is identify your top recurring signal and focus on eliminating it. Most
            traders have 1-2 patterns responsible for the majority of their preventable losses.
          </p>
        </section>
      </div>
    </div>
  );
}

function SignalCard({ name, desc, category }: { name: string; desc: string; category: string }) {
  const color = category === 'emotional'
    ? 'border-l-[var(--accent-yellow)]'
    : category === 'risk'
    ? 'border-l-[var(--accent-red)]'
    : 'border-l-[var(--accent-blue)]';

  return (
    <div className={`rounded-lg border border-[var(--border-color)] border-l-2 ${color} bg-[var(--bg-secondary)] p-3`}>
      <h3 className="text-sm font-semibold text-[var(--text-primary)]">{name}</h3>
      <p className="mt-1 text-xs">{desc}</p>
    </div>
  );
}
