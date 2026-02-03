export default function Disclaimer() {
  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="mb-6 text-3xl font-bold">Disclaimer</h1>

      <div className="space-y-4 text-sm leading-relaxed text-[var(--text-secondary)]">
        <p>
          Trading Buddy is an educational and analytical tool designed to help traders evaluate
          their own trade ideas. It is not a financial advisor, broker, or investment service.
        </p>

        <h2 className="text-lg font-medium text-[var(--text-primary)]">Not Financial Advice</h2>
        <p>
          Nothing provided by Trading Buddy constitutes financial advice, investment advice,
          trading advice, or any other sort of advice. The evaluations and scores are analytical
          outputs based on your inputs and declared preferences — they are not recommendations
          to buy, sell, or hold any security.
        </p>

        <h2 className="text-lg font-medium text-[var(--text-primary)]">No Guarantees</h2>
        <p>
          Trading Buddy does not guarantee the accuracy, completeness, or reliability of any
          evaluation. Past performance is not indicative of future results. All trading involves
          risk, including the risk of losing your entire investment.
        </p>

        <h2 className="text-lg font-medium text-[var(--text-primary)]">Your Responsibility</h2>
        <p>
          You are solely responsible for your trading decisions. Trading Buddy provides information
          to assist your decision-making process, but the final decision to execute a trade is
          always yours. You should consult with a qualified financial advisor before making any
          investment decisions.
        </p>

        <h2 className="text-lg font-medium text-[var(--text-primary)]">No Predictions</h2>
        <p>
          Trading Buddy does not predict future price movements, market conditions, or trade
          outcomes. Any scores, flags, or severity assessments reflect the quality of the trade
          setup relative to your own rules — not the probability of profit or loss.
        </p>
      </div>
    </div>
  );
}
