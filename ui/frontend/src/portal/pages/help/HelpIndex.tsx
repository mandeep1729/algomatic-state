import { Link } from 'react-router-dom';
import { ClipboardCheck, Brain, Flag, HelpCircle, Mail, LifeBuoy, ArrowRight } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

const SECTIONS: { title: string; desc: string; to: string; icon: LucideIcon; color: string }[] = [
  {
    title: 'Understanding Evaluations',
    desc: 'How trade evaluations work, what each dimension measures, and how to interpret scores.',
    to: '/help/evaluations',
    icon: ClipboardCheck,
    color: 'text-[var(--accent-blue)]',
  },
  {
    title: 'Behavioral Signals',
    desc: 'What behavioral flags mean and why they matter for your trading performance.',
    to: '/help/behavioral-signals',
    icon: Brain,
    color: 'text-[var(--accent-purple)]',
  },
  {
    title: 'Why We Flag Trades',
    desc: 'The reasoning behind trade flags and how severity levels are determined.',
    to: '/help/why-flags',
    icon: Flag,
    color: 'text-[var(--accent-yellow)]',
  },
  {
    title: 'Common Misunderstandings',
    desc: 'Clarifying common questions and misconceptions about how Trading Buddy works.',
    to: '/help/common-misunderstandings',
    icon: HelpCircle,
    color: 'text-[var(--accent-red)]',
  },
  {
    title: 'Contact Support',
    desc: 'Get in touch with our team for help or feedback.',
    to: '/help/contact',
    icon: Mail,
    color: 'text-[var(--accent-green)]',
  },
];

export default function HelpIndex() {
  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-4 flex items-center gap-3">
        <LifeBuoy size={28} className="text-[var(--accent-blue)]" />
        <h1 className="text-3xl font-bold">Help Center</h1>
      </div>
      <p className="mb-8 text-sm text-[var(--text-secondary)]">
        Guides and documentation to help you get the most out of Trading Buddy.
      </p>

      <div className="space-y-3">
        {SECTIONS.map((section) => {
          const Icon = section.icon;
          return (
            <Link
              key={section.to}
              to={section.to}
              className="flex items-center gap-4 rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4 transition-colors hover:border-[var(--accent-blue)]"
            >
              <Icon size={20} className={`flex-shrink-0 ${section.color}`} />
              <div className="flex-1">
                <h2 className="text-sm font-medium">{section.title}</h2>
                <p className="mt-1 text-xs text-[var(--text-secondary)]">{section.desc}</p>
              </div>
              <ArrowRight size={16} className="flex-shrink-0 text-[var(--text-secondary)]" />
            </Link>
          );
        })}
      </div>
    </div>
  );
}
