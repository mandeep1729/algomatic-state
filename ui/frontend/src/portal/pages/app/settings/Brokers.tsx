import { useEffect, useState } from 'react';
import api from '../../../api';
import type { BrokerStatus } from '../../../types';

export default function SettingsBrokers() {
  const [status, setStatus] = useState<BrokerStatus | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.fetchBrokerStatus().then(setStatus).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="p-8 text-[var(--text-secondary)]">Loading...</div>;

  return (
    <div className="p-6">
      <h1 className="mb-6 text-2xl font-semibold">Broker Integrations</h1>

      <div className="max-w-2xl space-y-6">
        {/* Connection status */}
        <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-5">
          <h2 className="mb-3 text-sm font-medium">Connection Status</h2>
          {status?.connected ? (
            <div className="space-y-3">
              {status.brokerages.map((broker) => (
                <div key={broker} className="flex items-center justify-between rounded-lg border border-[var(--border-color)] bg-[var(--bg-primary)] px-4 py-3">
                  <div className="flex items-center gap-3">
                    <span className="h-2.5 w-2.5 rounded-full bg-[var(--accent-green)]" />
                    <div>
                      <span className="text-sm font-medium">{broker}</span>
                      <span className="ml-2 text-xs text-[var(--accent-green)]">Connected</span>
                    </div>
                  </div>
                  <button className="text-xs text-[var(--accent-red)] hover:underline">
                    Disconnect
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-lg border border-dashed border-[var(--border-color)] bg-[var(--bg-primary)] p-6 text-center">
              <div className="mb-2 text-sm text-[var(--text-secondary)]">No brokers connected</div>
              <p className="mb-4 text-xs text-[var(--text-secondary)]">
                Connect your broker to automatically sync trades for evaluation.
              </p>
            </div>
          )}
        </div>

        {/* Add broker */}
        <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-5">
          <h2 className="mb-3 text-sm font-medium">Add a Broker</h2>
          <p className="mb-4 text-xs text-[var(--text-secondary)]">
            We use secure OAuth connections. Your credentials are never stored.
          </p>
          <div className="space-y-2">
            {['Robinhood', 'TD Ameritrade', 'Interactive Brokers', 'Alpaca'].map((broker) => {
              const isConnected = status?.brokerages.includes(broker);
              return (
                <div key={broker} className="flex items-center justify-between rounded-lg border border-[var(--border-color)] bg-[var(--bg-primary)] px-4 py-3">
                  <span className="text-sm">{broker}</span>
                  {isConnected ? (
                    <span className="text-xs text-[var(--accent-green)]">Connected</span>
                  ) : (
                    <button className="rounded-md border border-[var(--accent-blue)] px-3 py-1 text-xs font-medium text-[var(--accent-blue)] hover:bg-[var(--accent-blue)]/10 transition-colors">
                      Connect
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Sync info */}
        <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-5">
          <h2 className="mb-3 text-sm font-medium">Trade Sync</h2>
          <div className="space-y-2 text-xs text-[var(--text-secondary)]">
            <p>Connected brokers sync trades automatically every 15 minutes during market hours.</p>
            <p>You can also manually import trades via CSV from the Trades page.</p>
          </div>
          {status?.connected && (
            <button className="mt-3 rounded-md border border-[var(--border-color)] px-3 py-1.5 text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)]">
              Sync Now
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
