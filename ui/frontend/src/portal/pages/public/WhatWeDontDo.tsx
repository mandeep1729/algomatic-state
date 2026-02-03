import { Link } from 'react-router-dom';

const DONT_LIST = [
  {
    title: 'Predict Price Direction',
    desc: 'We never claim a stock will go up or down. Markets are uncertain, and anyone who says otherwise is selling you something.',
  },
  {
    title: 'Generate Buy/Sell Signals',
    desc: 'We don\'t tell you what to trade or when. You bring the trade idea — we help you stress-test it.',
  },
  {
    title: 'Claim High-Probability Outcomes',
    desc: 'There are no "90% win rate" promises here. We focus on process quality, not outcome prediction.',
  },
  {
    title: 'Replace Your Judgment',
    desc: 'The final decision is always yours. We surface information you may have overlooked, not commands to follow.',
  },
  {
    title: 'Optimize for Win Rate Alone',
    desc: 'A high win rate with poor risk management still loses money. We evaluate the full picture.',
  },
  {
    title: 'Automate Trade Execution',
    desc: 'We don\'t place trades on your behalf. We evaluate them — you decide whether to execute.',
  },
];

export default function WhatWeDontDo() {
  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="mb-4 text-3xl font-bold">What We Don't Do</h1>
      <p className="mb-10 text-sm text-[var(--text-secondary)]">
        Transparency about what this tool is not is just as important as explaining what it does.
        Trading Buddy is a mentor, not an oracle.
      </p>

      <div className="space-y-4">
        {DONT_LIST.map((item) => (
          <div key={item.title} className="flex gap-4 rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
            <span className="mt-0.5 flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-[var(--accent-red)]/10 text-sm text-[var(--accent-red)]">
              &times;
            </span>
            <div>
              <h2 className="text-sm font-medium">{item.title}</h2>
              <p className="mt-1 text-xs text-[var(--text-secondary)]">{item.desc}</p>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-10 rounded-lg border border-[var(--accent-green)]/30 bg-[var(--accent-green)]/5 p-5">
        <h3 className="text-sm font-semibold">What We Are</h3>
        <p className="mt-2 text-sm text-[var(--text-secondary)]">
          A risk guardian. A behavioral coach. A process enforcer. We help you make fewer
          preventable mistakes — one trade at a time.
        </p>
        <Link
          to="/how-it-works"
          className="mt-3 inline-block text-xs text-[var(--accent-blue)] hover:underline"
        >
          Learn how it works
        </Link>
      </div>
    </div>
  );
}
