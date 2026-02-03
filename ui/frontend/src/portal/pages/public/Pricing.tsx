import { Link } from 'react-router-dom';

const PLANS = [
  {
    name: 'Free',
    price: '$0',
    period: 'forever',
    features: [
      '5 evaluations per day',
      'All 6 evaluation dimensions',
      'Trade journal',
      'Basic insights',
    ],
    cta: 'Get Started',
    accent: false,
  },
  {
    name: 'Pro',
    price: '$19',
    period: '/month',
    features: [
      'Unlimited evaluations',
      'Broker sync (auto-import trades)',
      'Full behavioral analytics',
      'Strategy drift tracking',
      'Priority support',
    ],
    cta: 'Start Pro',
    accent: true,
  },
  {
    name: 'Team',
    price: '$49',
    period: '/month',
    features: [
      'Everything in Pro',
      'Up to 5 team members',
      'Shared strategy library',
      'Team performance dashboard',
      'Custom evaluation rules',
    ],
    cta: 'Contact Us',
    accent: false,
  },
];

export default function Pricing() {
  return (
    <div className="mx-auto max-w-4xl">
      <div className="mb-10 text-center">
        <h1 className="text-3xl font-bold">Pricing</h1>
        <p className="mt-3 text-sm text-[var(--text-secondary)]">
          Start free. Upgrade when you're ready for more.
        </p>
      </div>

      <div className="grid gap-6 sm:grid-cols-3">
        {PLANS.map((plan) => (
          <div
            key={plan.name}
            className={`rounded-lg border p-6 ${
              plan.accent
                ? 'border-[var(--accent-blue)] bg-[var(--accent-blue)]/5'
                : 'border-[var(--border-color)] bg-[var(--bg-secondary)]'
            }`}
          >
            <h2 className="text-lg font-semibold">{plan.name}</h2>
            <div className="mt-2 flex items-baseline gap-1">
              <span className="text-3xl font-bold">{plan.price}</span>
              <span className="text-sm text-[var(--text-secondary)]">{plan.period}</span>
            </div>
            <ul className="mt-4 space-y-2">
              {plan.features.map((f) => (
                <li key={f} className="flex items-start gap-2 text-sm text-[var(--text-secondary)]">
                  <span className="mt-0.5 text-[var(--accent-green)]">&#10003;</span>
                  {f}
                </li>
              ))}
            </ul>
            <Link
              to="/app"
              className={`mt-6 block rounded-md px-4 py-2 text-center text-sm font-medium ${
                plan.accent
                  ? 'bg-[var(--accent-blue)] text-white hover:opacity-90'
                  : 'border border-[var(--border-color)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
              }`}
            >
              {plan.cta}
            </Link>
          </div>
        ))}
      </div>

      <p className="mt-8 text-center text-xs text-[var(--text-secondary)]">
        All plans include a 14-day free trial of Pro features. No credit card required.
      </p>
    </div>
  );
}
