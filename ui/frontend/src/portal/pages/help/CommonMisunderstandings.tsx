import { HelpCircle, XCircle, CheckCircle2 } from 'lucide-react';

export default function HelpCommonMisunderstandings() {
  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-6 flex items-center gap-3">
        <HelpCircle size={28} className="text-[var(--accent-red)]" />
        <h1 className="text-3xl font-bold">Common Misunderstandings</h1>
      </div>

      <div className="space-y-4">
        {[
          {
            myth: '"A high score means the trade will be profitable"',
            reality: 'The score measures setup quality, not outcome probability. A well-structured trade can still lose money. What matters is that you\'re consistently taking well-structured trades — over time, good process produces good results.',
          },
          {
            myth: '"If there are no flags, the trade is safe"',
            reality: 'No flags means nothing we check was triggered — it doesn\'t mean the trade is risk-free. Markets are inherently uncertain. We evaluate process, not outcomes.',
          },
          {
            myth: '"Trading Buddy told me to take this trade"',
            reality: 'We never tell you to take a trade. We evaluate trades you\'re already considering and surface concerns. The decision is always yours.',
          },
          {
            myth: '"I should always skip flagged trades"',
            reality: 'Flags are prompts to think, not commands to stop. Some flags are informational. Others may be acceptable given your context. The key is making a deliberate decision, not an impulsive one.',
          },
          {
            myth: '"The system is wrong because my flagged trade made money"',
            reality: 'A profitable outcome doesn\'t validate a bad process. A trade without a stop loss that happens to work was still a bad decision. Results-oriented thinking is one of the biggest obstacles to long-term trading success.',
          },
          {
            myth: '"I only need to check evaluations for big trades"',
            reality: 'The biggest losses often come from small trades that violate discipline. A "quick scalp" with no stop loss or a "small position" that grows into revenge trading. Check everything.',
          },
          {
            myth: '"Behavioral signals are just opinions"',
            reality: 'Behavioral signals are pattern-detected, not opinion-based. They\'re derived from your own trading history — timing patterns, loss-recovery sequences, and comparison against your declared strategies.',
          },
          {
            myth: '"Once I set up my profile, I\'m done"',
            reality: 'Your trading profile, risk preferences, and strategies should evolve as you grow. Review and update them regularly. The evaluation is only as good as the rules you\'ve defined.',
          },
        ].map((item) => (
          <div key={item.myth} className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
            <div className="flex items-start gap-2 text-sm font-medium text-[var(--accent-red)]">
              <XCircle size={16} className="mt-0.5 flex-shrink-0" />
              {item.myth}
            </div>
            <div className="mt-2 flex items-start gap-2 text-xs text-[var(--text-secondary)]">
              <CheckCircle2 size={14} className="mt-0.5 flex-shrink-0 text-[var(--accent-green)]" />
              <p>{item.reality}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
