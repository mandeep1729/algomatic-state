import { useState } from 'react';
import { Link } from 'react-router-dom';

const FAQS = [
  {
    q: 'Is this a signal service?',
    a: 'No. We never generate buy/sell signals or predict price direction. We evaluate trades you are already considering to surface risk and blind spots.',
  },
  {
    q: 'Do I need to connect a broker?',
    a: 'No. You can manually enter trade ideas for evaluation. Connecting a broker simply automates trade import so you can review them after execution.',
  },
  {
    q: 'What does "blocker" mean?',
    a: 'A blocker is a finding severe enough that we recommend not taking the trade as-is. Common blockers include missing stop losses, extreme position sizing, or trading against a strong regime.',
  },
  {
    q: 'How is the evaluation score calculated?',
    a: 'The score (0-100) reflects the overall quality of the trade across all six evaluation dimensions. It penalizes issues based on severity — blockers have a large impact, info findings have none.',
  },
  {
    q: 'Can I customize which evaluators run?',
    a: 'Yes. In Settings > Evaluation Controls, you can toggle individual evaluators on or off and set a severity threshold for notifications.',
  },
  {
    q: 'Is my trading data shared with anyone?',
    a: 'No. Your data is never shared with third parties or used for advertising. Evaluations are processed using your data only.',
  },
  {
    q: 'What brokers do you support?',
    a: 'We currently support Robinhood, TD Ameritrade, Interactive Brokers, and Alpaca. More brokers are being added based on demand.',
  },
  {
    q: 'What is strategy drift?',
    a: 'Strategy drift measures how consistently you follow your own declared trading strategies. If you define a "Momentum Pullback" strategy but start taking random breakout trades, the drift score will reflect that inconsistency.',
  },
];

export default function FAQ() {
  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="mb-4 text-3xl font-bold">Frequently Asked Questions</h1>
      <p className="mb-10 text-sm text-[var(--text-secondary)]">
        Common questions about Trading Buddy and how it works.
      </p>

      <div className="space-y-2">
        {FAQS.map((faq) => (
          <FAQItem key={faq.q} question={faq.q} answer={faq.a} />
        ))}
      </div>

      <div className="mt-10 text-center text-sm text-[var(--text-secondary)]">
        Still have questions?{' '}
        <Link to="/help/contact" className="text-[var(--accent-blue)] hover:underline">
          Contact support
        </Link>
      </div>
    </div>
  );
}

function FAQItem({ question, answer }: { question: string; answer: string }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)]">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between px-4 py-3 text-left text-sm font-medium"
      >
        {question}
        <span className="ml-2 text-[var(--text-secondary)]">{open ? '\u2212' : '+'}</span>
      </button>
      {open && (
        <div className="border-t border-[var(--border-color)] px-4 py-3 text-sm text-[var(--text-secondary)]">
          {answer}
        </div>
      )}
    </div>
  );
}
