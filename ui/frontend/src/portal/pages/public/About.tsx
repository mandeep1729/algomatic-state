import { Link } from 'react-router-dom';

export default function About() {
  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="mb-4 text-3xl font-bold">About Trading Buddy</h1>

      <div className="space-y-6 text-sm leading-relaxed text-[var(--text-secondary)]">
        <p>
          Retail short-term traders consistently lose money — not because they lack indicators
          or technical analysis tools, but because of behavioral mistakes, poor risk discipline,
          and lack of contextual awareness.
        </p>

        <p>
          Trading Buddy was built to address this gap. We're not another charting platform or
          signal service. We're a mentor that sits between your trade idea and execution,
          surfacing what you might have missed.
        </p>

        <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-5">
          <h2 className="mb-3 text-lg font-medium text-[var(--text-primary)]">Our Mission</h2>
          <p>
            Prevent obvious trading mistakes before execution. Explain why a trade is risky
            in plain language. Focus on habits and discipline, not trade ideas. Be broker-agnostic
            and strategy-agnostic.
          </p>
        </div>

        <h2 className="text-lg font-medium text-[var(--text-primary)]">Principles</h2>

        <div className="grid gap-3 sm:grid-cols-2">
          {[
            { title: 'Risk-first', desc: 'Every evaluation starts with risk. If the risk is wrong, nothing else matters.' },
            { title: 'Process over outcome', desc: 'A good process with a bad outcome is still a good trade. We measure process quality.' },
            { title: 'Non-predictive', desc: 'We never predict where price will go. We evaluate what you can control.' },
            { title: 'Trader-specific', desc: 'Evaluations adapt to your declared strategies, risk tolerance, and behavioral patterns.' },
          ].map((p) => (
            <div key={p.title} className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
              <h3 className="text-sm font-semibold text-[var(--text-primary)]">{p.title}</h3>
              <p className="mt-1 text-xs">{p.desc}</p>
            </div>
          ))}
        </div>

        <p>
          Simple, explainable rules before advanced AI. We believe the best tool is one you
          trust because you understand how it works.
        </p>
      </div>

      <div className="mt-8 text-center">
        <Link
          to="/app"
          className="inline-block rounded-md bg-[var(--accent-blue)] px-6 py-3 text-sm font-medium text-white hover:opacity-90"
        >
          Start Using Trading Buddy
        </Link>
      </div>
    </div>
  );
}
