export default function Terms() {
  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="mb-6 text-3xl font-bold">Terms of Service</h1>

      <div className="space-y-4 text-sm leading-relaxed text-[var(--text-secondary)]">
        <p>
          By using Trading Buddy, you agree to the following terms and conditions.
        </p>

        <h2 className="text-lg font-medium text-[var(--text-primary)]">1. Acceptance of Terms</h2>
        <p>
          By accessing or using Trading Buddy, you agree to be bound by these Terms of Service.
          If you do not agree, do not use the service.
        </p>

        <h2 className="text-lg font-medium text-[var(--text-primary)]">2. Service Description</h2>
        <p>
          Trading Buddy is a trade evaluation platform that analyzes proposed trades against
          risk, behavioral, and contextual dimensions. It is an educational tool, not a
          financial advisory service.
        </p>

        <h2 className="text-lg font-medium text-[var(--text-primary)]">3. User Responsibilities</h2>
        <p>
          You are responsible for the accuracy of the information you provide, including trade
          parameters and strategy definitions. You are solely responsible for all trading
          decisions made using or informed by this service.
        </p>

        <h2 className="text-lg font-medium text-[var(--text-primary)]">4. Broker Connections</h2>
        <p>
          When you connect a broker, we use secure OAuth connections to access your trade
          history. We do not store your broker credentials. We do not execute trades on your
          behalf. You can disconnect your broker at any time.
        </p>

        <h2 className="text-lg font-medium text-[var(--text-primary)]">5. Data Usage</h2>
        <p>
          Your trading data is used solely to provide evaluation services to you. We do not
          sell, share, or distribute your personal or trading data to third parties.
        </p>

        <h2 className="text-lg font-medium text-[var(--text-primary)]">6. Limitation of Liability</h2>
        <p>
          Trading Buddy is provided "as is" without warranties of any kind. We are not liable
          for any trading losses, missed opportunities, or damages arising from the use of
          this service.
        </p>

        <h2 className="text-lg font-medium text-[var(--text-primary)]">7. Changes to Terms</h2>
        <p>
          We may update these terms from time to time. Continued use of the service after
          changes constitutes acceptance of the new terms.
        </p>
      </div>
    </div>
  );
}
