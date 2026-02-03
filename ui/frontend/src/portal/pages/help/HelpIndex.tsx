import { Link } from 'react-router-dom';

const SECTIONS = [
  {
    title: 'Understanding Evaluations',
    desc: 'How trade evaluations work, what each dimension measures, and how to interpret scores.',
    to: '/help/evaluations',
  },
  {
    title: 'Behavioral Signals',
    desc: 'What behavioral flags mean and why they matter for your trading performance.',
    to: '/help/behavioral-signals',
  },
  {
    title: 'Why We Flag Trades',
    desc: 'The reasoning behind trade flags and how severity levels are determined.',
    to: '/help/why-flags',
  },
  {
    title: 'Common Misunderstandings',
    desc: 'Clarifying common questions and misconceptions about how Trading Buddy works.',
    to: '/help/common-misunderstandings',
  },
  {
    title: 'Contact Support',
    desc: 'Get in touch with our team for help or feedback.',
    to: '/help/contact',
  },
];

export default function HelpIndex() {
  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="mb-4 text-3xl font-bold">Help Center</h1>
      <p className="mb-8 text-sm text-[var(--text-secondary)]">
        Guides and documentation to help you get the most out of Trading Buddy.
      </p>

      <div className="space-y-3">
        {SECTIONS.map((section) => (
          <Link
            key={section.to}
            to={section.to}
            className="block rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4 transition-colors hover:border-[var(--accent-blue)]"
          >
            <h2 className="text-sm font-medium">{section.title}</h2>
            <p className="mt-1 text-xs text-[var(--text-secondary)]">{section.desc}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
