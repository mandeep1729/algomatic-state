import { Link } from 'react-router-dom';
import { FileEdit, Layers, MessageSquareWarning, CheckCircle2, ArrowRight, Quote } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

const STEPS: { icon: LucideIcon; color: string; title: string; desc: string }[] = [
  {
    icon: FileEdit,
    color: 'bg-[var(--accent-blue)]',
    title: 'Submit Your Trade Idea',
    desc: 'Enter the symbol, direction, entry price, stop loss, and profit target. Optionally add your rationale.',
  },
  {
    icon: Layers,
    color: 'bg-[var(--accent-purple)]',
    title: 'Multi-Dimensional Evaluation',
    desc: 'Your trade is evaluated across six dimensions: regime fit, entry timing, exit logic, risk positioning, behavioral signals, and strategy consistency.',
  },
  {
    icon: MessageSquareWarning,
    color: 'bg-[var(--accent-yellow)]',
    title: 'Get Actionable Feedback',
    desc: 'Each dimension produces findings with severity levels — info, warning, critical, or blocker. You see exactly what the system flagged and why.',
  },
  {
    icon: CheckCircle2,
    color: 'bg-[var(--accent-green)]',
    title: 'Decide With Confidence',
    desc: 'Use the evaluation to confirm your thesis or identify blind spots. The decision is always yours — we just surface what you might have missed.',
  },
];

export default function HowItWorks() {
  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="mb-4 text-3xl font-bold">How It Works</h1>
      <p className="mb-10 text-sm text-[var(--text-secondary)]">
        Trading Buddy acts as a second set of eyes — quietly reviewing your proposed trade
        and highlighting what you may have overlooked.
      </p>

      <div className="space-y-8">
        {STEPS.map((s, i) => {
          const Icon = s.icon;
          return (
            <div key={i} className="flex gap-4">
              <div className={`flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full ${s.color} text-white`}>
                <Icon size={16} />
              </div>
              <div>
                <h2 className="text-lg font-medium">{s.title}</h2>
                <p className="mt-1 text-sm text-[var(--text-secondary)]">{s.desc}</p>
              </div>
            </div>
          );
        })}
      </div>

      <div className="mt-12 rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-6">
        <div className="mb-2 flex items-center gap-2">
          <Quote size={16} className="text-[var(--accent-blue)]" />
          <h3 className="text-sm font-semibold">Core Philosophy</h3>
        </div>
        <p className="text-sm text-[var(--text-secondary)] leading-relaxed">
          "Slow the trader down, not tell them what to do." We exist to improve decision quality,
          reduce preventable mistakes, encourage discipline, and surface contextual risk.
          We never predict outcomes or generate signals.
        </p>
      </div>

      <div className="mt-8 text-center">
        <Link
          to="/app/evaluate"
          className="inline-flex items-center gap-2 rounded-md bg-[var(--accent-blue)] px-6 py-3 text-sm font-medium text-white transition-opacity duration-150 hover:opacity-90"
        >
          Try an Evaluation
          <ArrowRight size={16} />
        </Link>
      </div>
    </div>
  );
}
