import { useState, type FormEvent } from 'react';
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
  CheckCircle2,
  Loader2,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { apiUrl } from '../../../config';

const FEATURES: { title: string; desc: string; icon: LucideIcon; color: string; gradient: string }[] = [
  {
    title: 'Risk Guardian',
    desc: 'Automated checks for stop loss placement, position sizing, and risk:reward ratios before you execute.',
    icon: ShieldAlert,
    color: 'text-red-400',
    gradient: 'from-red-500/20 to-orange-500/5',
  },
  {
    title: 'Behavioral Coach',
    desc: 'Real-time detection of revenge trading, FOMO, and tilt. Get alerted before emotions cost you money.',
    icon: Brain,
    color: 'text-purple-400',
    gradient: 'from-purple-500/20 to-pink-500/5',
  },
  {
    title: 'Regime Awareness',
    desc: 'Align your trades with current market conditions. Don\'t fight the trend or chop.',
    icon: Activity,
    color: 'text-blue-400',
    gradient: 'from-blue-500/20 to-cyan-500/5',
  },
  {
    title: 'Strategy Consistency',
    desc: 'Drift detection ensures you stick to your playbook. No more random improvisation.',
    icon: GitCompare,
    color: 'text-yellow-400',
    gradient: 'from-yellow-500/20 to-amber-500/5',
  },
  {
    title: 'Timing Review',
    desc: 'Analysis of entry timing relative to volatility and session opens.',
    icon: Clock,
    color: 'text-green-400',
    gradient: 'from-green-500/20 to-emerald-500/5',
  },
  {
    title: 'Trade Journal',
    desc: 'Automatic journaling with mood tracking and deep performance analytics.',
    icon: BookOpen,
    color: 'text-indigo-400',
    gradient: 'from-indigo-500/20 to-violet-500/5',
  },
];

export default function Home() {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<{ ok: boolean; message: string } | null>(null);

  async function handleWaitlistSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setResult(null);
    try {
      const res = await fetch(apiUrl('/api/waitlist'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: name.trim(), email: email.trim() }),
      });
      const data = await res.json();
      if (res.ok) {
        setResult({ ok: true, message: data.message });
        setName('');
        setEmail('');
      } else {
        setResult({ ok: false, message: data.detail || 'Something went wrong.' });
      }
    } catch {
      setResult({ ok: false, message: 'Network error. Please try again.' });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex flex-col gap-24">
      {/* Hero */}
      <section className="relative flex flex-col items-center text-center">
        {/* Background Gradients */}
        <div className="absolute -top-32 -z-10 h-[500px] w-[500px] rounded-full bg-[var(--accent-blue)]/20 blur-[100px]" />
        <div className="absolute -bottom-32 -right-32 -z-10 h-[500px] w-[500px] rounded-full bg-[var(--accent-purple)]/10 blur-[100px]" />

        <div className="inline-flex items-center gap-2 rounded-full border border-[var(--accent-blue)]/30 bg-[var(--accent-blue)]/10 px-3 py-1 text-xs font-medium text-[var(--accent-blue)]">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[var(--accent-blue)] opacity-75"></span>
            <span className="relative inline-flex h-2 w-2 rounded-full bg-[var(--accent-blue)]"></span>
          </span>
          AI-Powered Trading Assistant
        </div>

        <h1 className="mt-8 max-w-4xl text-5xl font-bold tracking-tight sm:text-7xl">
          Your Trading <br />
          <span className="bg-gradient-to-r from-[var(--accent-blue)] to-[var(--accent-purple)] bg-clip-text text-transparent">
            Second Opinion
          </span>
        </h1>

        <p className="mt-6 max-w-2xl text-lg text-[var(--text-secondary)]">
          Trading Buddy reviews your trades <strong>before</strong> you execute. Surface hidden risks, flag behavioral flaws, and build discipline without reliable logic.
        </p>

        <div className="mt-10 flex gap-4">
          <a
            href="#waitlist"
            className="group flex items-center gap-2 rounded-full bg-[var(--accent-blue)] px-8 py-3.5 text-sm font-semibold text-white shadow-lg shadow-[var(--accent-blue)]/25 transition-all hover:bg-[var(--accent-blue)]/90 hover:shadow-[var(--accent-blue)]/40 hover:-translate-y-0.5"
          >
            Join Waitlist
            <ArrowRight size={16} className="transition-transform group-hover:translate-x-0.5" />
          </a>
          <Link
            to="/how-it-works"
            className="flex items-center gap-2 rounded-full border border-[var(--border-color)] bg-[var(--bg-secondary)] px-8 py-3.5 text-sm font-semibold text-[var(--text-secondary)] transition-all hover:border-[var(--text-primary)] hover:text-[var(--text-primary)]"
          >
            How It Works
          </Link>
        </div>

        {/* Hero Stats/Social Proof (Mock) */}
        <div className="mt-16 grid grid-cols-2 gap-8 border-t border-[var(--border-color)] pt-8 sm:grid-cols-4 lg:w-full lg:max-w-4xl">
          {[
            { label: 'Trades Analyzed', value: '10k+' },
            { label: 'Risk Detected', value: '$2M+' },
            { label: 'Active Traders', value: '500+' },
            { label: 'Uptime', value: '99.9%' },
          ].map((stat) => (
            <div key={stat.label}>
              <div className="text-2xl font-bold text-[var(--text-primary)]">{stat.value}</div>
              <div className="text-xs uppercase tracking-wider text-[var(--text-secondary)]">{stat.label}</div>
            </div>
          ))}
        </div>
      </section>

      {/* What we do */}
      <section>
        <div className="mb-12 text-center">
          <h2 className="text-3xl font-bold tracking-tight">Everything you need to stay disciplined</h2>
          <p className="mt-4 text-[var(--text-secondary)]">Automated checks that act as your risk manager.</p>
        </div>

        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((item) => {
            const Icon = item.icon;
            return (
              <div key={item.title} className="group relative overflow-hidden rounded-2xl border border-[var(--border-color)] bg-[var(--bg-secondary)] p-6 transition-all hover:border-[var(--text-secondary)]/30 hover:shadow-xl">
                <div className={`absolute inset-0 bg-gradient-to-br ${item.gradient} opacity-0 transition-opacity group-hover:opacity-100`} />
                <div className="relative z-10">
                  <div className={`mb-4 inline-flex rounded-lg bg-[var(--bg-tertiary)] p-3 ${item.color}`}>
                    <Icon size={24} />
                  </div>
                  <h3 className="mb-2 text-lg font-semibold">{item.title}</h3>
                  <p className="text-sm leading-relaxed text-[var(--text-secondary)]">{item.desc}</p>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* Comparison / What we don't do */}
      <section className="rounded-3xl border border-[var(--border-color)] bg-[var(--bg-secondary)]/30 p-8 sm:p-12">
        <div className="grid gap-12 lg:grid-cols-2 lg:gap-24">
          <div>
            <h2 className="text-3xl font-bold tracking-tight">We are NOT a signal provider.</h2>
            <p className="mt-4 text-lg text-[var(--text-secondary)]">
              Most tools try to predict the market. We try to predict <strong>you</strong>. Trading Buddy focuses entirely on your execution, risk management, and psychology.
            </p>
            <div className="mt-8 space-y-4">
              {[
                'We do NOT predict price direction.',
                'We do NOT generate buy/sell signals.',
                'We do NOT promise accurate forecasts.',
              ].map((text) => (
                <div key={text} className="flex items-center gap-3 text-[var(--text-secondary)]">
                  <div className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-[var(--accent-red)]/10 text-[var(--accent-red)]">
                    <X size={14} strokeWidth={3} />
                  </div>
                  <span>{text}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="space-y-6">
            <h3 className="text-xl font-semibold">What we actually do:</h3>
            <div className="space-y-4">
              {[
                'Flag unplanned trades immediately',
                'Calculate max position size based on volatility',
                'Detect "revenge trading" patterns',
                'Force you to verify checklist before entry',
                'Track emotional state alongside P&L'
              ].map((text) => (
                <div key={text} className="flex items-center gap-3">
                  <div className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-[var(--accent-green)]/10 text-[var(--accent-green)]">
                    <CheckCircle2 size={14} strokeWidth={3} />
                  </div>
                  <span className="text-[var(--text-primary)]">{text}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Waitlist CTA */}
      <section
        id="waitlist"
        className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-[var(--accent-blue)] via-blue-600 to-[var(--accent-purple)] px-6 py-16 text-center text-white sm:px-12 lg:py-24"
      >
        {/* Abstract shapes */}
        <div className="absolute left-0 top-0 h-64 w-64 -translate-x-1/2 -translate-y-1/2 rounded-full bg-white/10 blur-3xl"></div>
        <div className="absolute bottom-0 right-0 h-64 w-64 translate-x-1/2 translate-y-1/2 rounded-full bg-purple-500/20 blur-3xl"></div>

        <div className="relative z-10 mx-auto max-w-2xl">
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">Slow down. Trade better.</h2>
          <p className="mt-4 text-lg text-blue-100">
            Join disciplined traders who use Trading Buddy to protect their capital from themselves.
          </p>

          {result?.ok ? (
            <div className="mt-10 rounded-xl bg-white/15 px-6 py-4">
              <CheckCircle2 size={24} className="mx-auto mb-2 text-green-300" />
              <p className="text-sm font-medium">{result.message}</p>
            </div>
          ) : (
            <form
              onSubmit={handleWaitlistSubmit}
              className="mx-auto mt-10 flex max-w-md flex-col gap-3 sm:flex-row"
            >
              <input
                type="text"
                placeholder="Your name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                className="flex-1 rounded-full border border-white/20 bg-white/10 px-5 py-3 text-sm text-white placeholder-blue-200 outline-none transition focus:border-white/40 focus:bg-white/15"
              />
              <input
                type="email"
                placeholder="Your email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="flex-1 rounded-full border border-white/20 bg-white/10 px-5 py-3 text-sm text-white placeholder-blue-200 outline-none transition focus:border-white/40 focus:bg-white/15"
              />
              <button
                type="submit"
                disabled={submitting}
                className="group inline-flex items-center justify-center gap-2 rounded-full bg-white px-8 py-3 text-sm font-bold text-blue-600 shadow-xl transition-all hover:bg-blue-50 hover:shadow-2xl hover:-translate-y-0.5 disabled:opacity-60"
              >
                {submitting ? (
                  <Loader2 size={16} className="animate-spin" />
                ) : (
                  <>
                    Join Waitlist
                    <ArrowRight size={16} className="transition-transform group-hover:translate-x-0.5" />
                  </>
                )}
              </button>
            </form>
          )}

          {result && !result.ok && (
            <p className="mt-3 text-sm text-red-200">{result.message}</p>
          )}
        </div>
      </section>
    </div>
  );
}
