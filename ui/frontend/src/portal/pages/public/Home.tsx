import { Link } from 'react-router-dom';
import {
  ShieldAlert,
  Brain,
  Activity,
  GitCompare,
  Clock,
  BookOpen,
  X,
  ArrowRight,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

const FEATURES: { title: string; desc: string; icon: LucideIcon; color: string }[] = [
  {
    title: 'Risk Guardian',
    desc: 'Checks every trade against your risk rules — stop loss placement, position sizing, risk:reward ratio.',
    icon: ShieldAlert,
    color: 'text-[var(--accent-red)]',
  },
  {
    title: 'Behavioral Coach',
    desc: 'Detects patterns like revenge trading, FOMO entries, and overconfidence before they cost you money.',
    icon: Brain,
    color: 'text-[var(--accent-purple)]',
  },
  {
    title: 'Regime Awareness',
    desc: 'Evaluates whether your trade direction aligns with the current market regime.',
    icon: Activity,
    color: 'text-[var(--accent-blue)]',
  },
  {
    title: 'Strategy Consistency',
    desc: 'Compares each trade against your declared strategies to catch drift and improvisation.',
    icon: GitCompare,
    color: 'text-[var(--accent-yellow)]',
  },
  {
    title: 'Timing Review',
    desc: 'Flags rushed entries, trades during extreme volatility, and suboptimal timing windows.',
    icon: Clock,
    color: 'text-[var(--accent-green)]',
  },
  {
    title: 'Trade Journal',
    desc: 'Built-in journaling with mood tracking, behavioral tags, and trade linking for self-reflection.',
    icon: BookOpen,
    color: 'text-[var(--accent-blue)]',
  },
];

export default function Home() {
  return (
    <div>
      {/* Hero */}
      <section className="py-16 text-center">
        <h1 className="text-4xl font-bold leading-tight sm:text-5xl">
          Your Trading Second Opinion
        </h1>
        <p className="mx-auto mt-4 max-w-2xl text-lg text-[var(--text-secondary)]">
          Trading Buddy reviews your trades before you execute. We surface risk, flag behavioral mistakes,
          and help you build discipline — without predicting prices or selling signals.
        </p>
        <div className="mt-8 flex justify-center gap-4">
          <Link
            to="/app"
            className="flex items-center gap-2 rounded-md bg-[var(--accent-blue)] px-6 py-3 text-sm font-medium text-white transition-opacity duration-150 hover:opacity-90"
          >
            Open App
            <ArrowRight size={16} />
          </Link>
          <Link
            to="/how-it-works"
            className="rounded-md border border-[var(--border-color)] px-6 py-3 text-sm font-medium text-[var(--text-secondary)] transition-colors duration-150 hover:text-[var(--text-primary)]"
          >
            How It Works
          </Link>
        </div>
      </section>

      {/* What we do */}
      <section className="border-t border-[var(--border-color)] py-12">
        <h2 className="mb-8 text-center text-2xl font-semibold">What Trading Buddy Does</h2>
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((item) => {
            const Icon = item.icon;
            return (
              <div key={item.title} className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-5 transition-colors duration-150 hover:border-[var(--accent-blue)]/40">
                <div className="mb-3 flex items-center gap-2.5">
                  <Icon size={18} className={item.color} />
                  <h3 className="text-sm font-semibold">{item.title}</h3>
                </div>
                <p className="text-xs leading-relaxed text-[var(--text-secondary)]">{item.desc}</p>
              </div>
            );
          })}
        </div>
      </section>

      {/* What we don't do */}
      <section className="border-t border-[var(--border-color)] py-12">
        <h2 className="mb-4 text-center text-2xl font-semibold">What We Don't Do</h2>
        <p className="mx-auto mb-8 max-w-xl text-center text-sm text-[var(--text-secondary)]">
          We're not a signal service. We don't predict prices. We don't tell you what to trade.
        </p>
        <div className="mx-auto grid max-w-3xl gap-3 sm:grid-cols-2">
          {[
            'Predict price direction',
            'Generate buy/sell signals',
            'Claim high-probability outcomes',
            'Replace your judgment',
            'Optimize for win rate alone',
            'Automate trade execution',
          ].map((item) => (
            <div key={item} className="flex items-center gap-2.5 text-sm text-[var(--text-secondary)]">
              <X size={14} className="flex-shrink-0 text-[var(--accent-red)]" />
              {item}
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="border-t border-[var(--border-color)] py-12 text-center">
        <h2 className="text-xl font-semibold">Slow down. Trade better.</h2>
        <p className="mt-2 text-sm text-[var(--text-secondary)]">
          Start evaluating your trades today.
        </p>
        <Link
          to="/app/evaluate"
          className="mt-6 inline-flex items-center gap-2 rounded-md bg-[var(--accent-blue)] px-6 py-3 text-sm font-medium text-white transition-opacity duration-150 hover:opacity-90"
        >
          Evaluate a Trade
          <ArrowRight size={16} />
        </Link>
      </section>
    </div>
  );
}
