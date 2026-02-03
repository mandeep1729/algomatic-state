export default function Privacy() {
  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="mb-6 text-3xl font-bold">Privacy Policy</h1>

      <div className="space-y-4 text-sm leading-relaxed text-[var(--text-secondary)]">
        <p>
          Your privacy matters to us. This policy explains what data we collect, how we use it,
          and your rights.
        </p>

        <h2 className="text-lg font-medium text-[var(--text-primary)]">What We Collect</h2>
        <ul className="ml-4 list-disc space-y-1">
          <li>Account information (name, email)</li>
          <li>Trading profile and preferences you configure</li>
          <li>Trade data (entered manually or synced from connected brokers)</li>
          <li>Journal entries and behavioral tags</li>
          <li>Evaluation results and usage patterns</li>
        </ul>

        <h2 className="text-lg font-medium text-[var(--text-primary)]">How We Use Your Data</h2>
        <ul className="ml-4 list-disc space-y-1">
          <li>Providing trade evaluations against your personal risk rules and strategies</li>
          <li>Generating behavioral insights and performance analytics</li>
          <li>Improving the evaluation algorithms (aggregated, anonymized data only)</li>
        </ul>

        <h2 className="text-lg font-medium text-[var(--text-primary)]">What We Don't Do</h2>
        <ul className="ml-4 list-disc space-y-1">
          <li>Sell your data to third parties</li>
          <li>Share your individual trading data with anyone</li>
          <li>Use your data for advertising</li>
          <li>Train models on your personal information</li>
        </ul>

        <h2 className="text-lg font-medium text-[var(--text-primary)]">Broker Connections</h2>
        <p>
          When you connect a broker, we use secure OAuth to access your trade history.
          We never store your broker login credentials. You can disconnect and revoke
          access at any time.
        </p>

        <h2 className="text-lg font-medium text-[var(--text-primary)]">Data Retention</h2>
        <p>
          Your data is retained as long as your account is active. You can export or delete
          your data at any time from Settings &gt; Data &amp; Privacy. Account deletion
          permanently removes all associated data.
        </p>

        <h2 className="text-lg font-medium text-[var(--text-primary)]">Your Rights</h2>
        <p>
          You have the right to access, export, correct, or delete your personal data.
          Contact us at support to exercise these rights.
        </p>
      </div>
    </div>
  );
}
