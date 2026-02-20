import { useEffect, useState, useMemo, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import api from '../../../api';
import type { BrokerageInfo, ConnectionStatusDetail } from '../../../types';

export default function SettingsBrokers() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [brokerages, setBrokerages] = useState<BrokerageInfo[]>([]);
  const [connections, setConnections] = useState<ConnectionStatusDetail | null>(null);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [connecting, setConnecting] = useState<string | null>(null);
  const [disconnecting, setDisconnecting] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [syncResult, setSyncResult] = useState<string | null>(null);
  const [callbackStatus, setCallbackStatus] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setError(null);
    try {
      const [brokerageRes, connRes] = await Promise.all([
        api.fetchBrokerages(),
        api.fetchBrokerConnections(),
      ]);
      setBrokerages(brokerageRes.brokerages);
      setConnections(connRes);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load broker data');
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial load + handle OAuth callback status
  useEffect(() => {
    loadData();

    const status = searchParams.get('status');
    if (status) {
      if (status === 'success') {
        setCallbackStatus('Broker connected successfully!');
      } else {
        setCallbackStatus(`Connection returned with status: ${status}`);
      }
      // Clean up query params
      searchParams.delete('status');
      setSearchParams(searchParams, { replace: true });
    }
  }, [loadData, searchParams, setSearchParams]);

  // Clear callback status after 5s
  useEffect(() => {
    if (!callbackStatus) return;
    const timer = setTimeout(() => setCallbackStatus(null), 5000);
    return () => clearTimeout(timer);
  }, [callbackStatus]);

  // Derive connected slugs for splitting available vs connected
  const connectedSlugs = useMemo(() => {
    if (!connections?.connections) return new Set<string>();
    return new Set(connections.connections.map((c) => c.brokerage_slug));
  }, [connections]);

  const connectedBrokerages = useMemo(
    () => brokerages.filter((b) => connectedSlugs.has(b.slug)),
    [brokerages, connectedSlugs],
  );

  const availableBrokerages = useMemo(() => {
    let available = brokerages.filter((b) => !connectedSlugs.has(b.slug));
    if (search.trim()) {
      const q = search.toLowerCase();
      available = available.filter(
        (b) =>
          b.display_name.toLowerCase().includes(q) ||
          b.name.toLowerCase().includes(q) ||
          (b.description && b.description.toLowerCase().includes(q)),
      );
    }
    return available;
  }, [brokerages, connectedSlugs, search]);

  async function handleConnect(slug: string) {
    setConnecting(slug);
    setError(null);
    try {
      const returnUrl = `${window.location.origin}/app/settings/brokers?status=success`;
      const res = await api.connectBroker(slug, returnUrl);
      window.location.href = res.redirect_url;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to connect broker');
      setConnecting(null);
    }
  }

  async function handleDisconnect(authorizationId: string) {
    if (!window.confirm('Are you sure you want to disconnect this broker?')) return;
    setDisconnecting(authorizationId);
    setError(null);
    try {
      await api.disconnectBroker(authorizationId);
      // Refresh connections
      const connRes = await api.fetchBrokerConnections();
      setConnections(connRes);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to disconnect broker');
    } finally {
      setDisconnecting(null);
    }
  }

  async function handleSync() {
    setSyncing(true);
    setSyncResult(null);
    setError(null);
    try {
      const res = await api.syncBrokerData();
      setSyncResult(`Synced ${res.trades_synced} trades${res.campaigns_created ? `, ${res.campaigns_created} campaigns created` : ''}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sync failed');
    } finally {
      setSyncing(false);
    }
  }

  if (loading) {
    return <div className="p-8 text-[var(--text-secondary)]">Loading brokers...</div>;
  }

  return (
    <div className="p-6">
      <h1 className="mb-6 text-2xl font-semibold">Broker Integrations</h1>

      {/* Feedback banners */}
      {callbackStatus && (
        <div className="mb-4 rounded-lg border border-[var(--accent-green)]/30 bg-[var(--accent-green)]/10 px-4 py-3 text-sm text-[var(--accent-green)]">
          {callbackStatus}
        </div>
      )}
      {error && (
        <div className="mb-4 rounded-lg border border-[var(--accent-red)]/30 bg-[var(--accent-red)]/10 px-4 py-3 text-sm text-[var(--accent-red)]">
          {error}
        </div>
      )}

      <div className="max-w-3xl space-y-6">
        {/* Section 1: Connected Brokers */}
        <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-5">
          <h2 className="mb-3 text-sm font-medium">Connected Brokers</h2>

          {connections && connections.connections.length > 0 ? (
            <div className="space-y-2">
              {connections.connections.map((conn) => {
                const matchedBrokerage = connectedBrokerages.find(
                  (b) => b.slug === conn.brokerage_slug,
                );
                return (
                  <div
                    key={conn.authorization_id}
                    className="flex items-center justify-between rounded-lg border border-[var(--border-color)] bg-[var(--bg-primary)] px-4 py-3"
                  >
                    <div className="flex items-center gap-3">
                      <BrokerLogo
                        url={conn.brokerage_logo_url ?? matchedBrokerage?.square_logo_url}
                        name={conn.brokerage_name}
                      />
                      <div>
                        <span className="text-sm font-medium">{conn.brokerage_name}</span>
                        <span className="ml-2 inline-flex items-center gap-1 text-xs text-[var(--accent-green)]">
                          <span className="inline-block h-1.5 w-1.5 rounded-full bg-[var(--accent-green)]" />
                          Connected
                        </span>
                        {conn.created_date && (
                          <span className="ml-2 text-xs text-[var(--text-secondary)]">
                            since {new Date(conn.created_date).toLocaleDateString()}
                          </span>
                        )}
                        {conn.disabled && (
                          <span className="ml-2 text-xs text-[var(--accent-yellow)]">
                            (disabled)
                          </span>
                        )}
                      </div>
                    </div>
                    <button
                      onClick={() => handleDisconnect(conn.authorization_id)}
                      disabled={disconnecting === conn.authorization_id}
                      className="text-xs text-[var(--accent-red)] hover:underline disabled:opacity-50"
                    >
                      {disconnecting === conn.authorization_id ? 'Disconnecting...' : 'Disconnect'}
                    </button>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="rounded-lg border border-dashed border-[var(--border-color)] bg-[var(--bg-primary)] p-6 text-center">
              <div className="mb-2 text-sm text-[var(--text-secondary)]">No brokers connected</div>
              <p className="text-xs text-[var(--text-secondary)]">
                Connect your broker below to automatically sync trades for evaluation.
              </p>
            </div>
          )}
        </div>

        {/* Section 2: Add a Broker */}
        <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-5">
          <h2 className="mb-2 text-sm font-medium">Add a Broker</h2>
          <p className="mb-4 text-xs text-[var(--text-secondary)]">
            We use secure OAuth connections via SnapTrade. Your credentials are never stored.
          </p>

          {/* Search input */}
          <div className="mb-4">
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={`Search ${brokerages.length}+ supported brokerages...`}
              className="w-full rounded-md border border-[var(--border-color)] bg-[var(--bg-primary)] px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-secondary)] focus:border-[var(--accent-blue)] focus:outline-none"
            />
          </div>

          {/* Brokerage grid */}
          {availableBrokerages.length > 0 ? (
            <div className="grid gap-2 sm:grid-cols-2">
              {availableBrokerages.map((b) => (
                <div
                  key={b.id}
                  className="flex items-center justify-between rounded-lg border border-[var(--border-color)] bg-[var(--bg-primary)] px-4 py-3"
                >
                  <div className="flex items-center gap-3 overflow-hidden">
                    <BrokerLogo url={b.square_logo_url ?? b.logo_url} name={b.display_name} />
                    <div className="min-w-0">
                      <div className="truncate text-sm font-medium">{b.display_name}</div>
                      {b.description && (
                        <div className="truncate text-xs text-[var(--text-secondary)]">
                          {b.description}
                        </div>
                      )}
                      {b.maintenance_mode && (
                        <span className="text-[10px] font-medium text-[var(--accent-yellow)]">
                          Maintenance
                        </span>
                      )}
                    </div>
                  </div>
                  <button
                    onClick={() => handleConnect(b.slug)}
                    disabled={b.maintenance_mode || connecting === b.slug}
                    className="ml-3 shrink-0 rounded-md border border-[var(--accent-blue)] px-3 py-1 text-xs font-medium text-[var(--accent-blue)] transition-colors hover:bg-[var(--accent-blue)]/10 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    {connecting === b.slug ? 'Connecting...' : 'Connect'}
                  </button>
                </div>
              ))}
            </div>
          ) : search.trim() ? (
            <div className="rounded-lg border border-dashed border-[var(--border-color)] bg-[var(--bg-primary)] p-6 text-center text-sm text-[var(--text-secondary)]">
              No brokerages match &ldquo;{search}&rdquo;
            </div>
          ) : (
            <div className="rounded-lg border border-dashed border-[var(--border-color)] bg-[var(--bg-primary)] p-6 text-center text-sm text-[var(--text-secondary)]">
              All available brokerages are already connected.
            </div>
          )}
        </div>

        {/* Section 3: Trade Sync */}
        <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-5">
          <h2 className="mb-3 text-sm font-medium">Trade Sync</h2>
          <div className="space-y-2 text-xs text-[var(--text-secondary)]">
            <p>Connected brokers sync trades automatically every 15 minutes during market hours.</p>
            <p>You can also manually import trades via CSV from the Trades page.</p>
          </div>

          <div className="mt-3 flex items-center gap-3">
            <button
              onClick={handleSync}
              disabled={syncing || !connections?.connected}
              className="rounded-md border border-[var(--border-color)] px-3 py-1.5 text-xs text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)] disabled:cursor-not-allowed disabled:opacity-40"
            >
              {syncing ? 'Syncing...' : 'Sync Now'}
            </button>

            {syncResult && (
              <span className="text-xs text-[var(--accent-green)]">{syncResult}</span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

/** Renders a broker logo image with a letter fallback. */
function BrokerLogo({ url, name }: { url?: string | null; name: string }) {
  const [imgError, setImgError] = useState(false);
  const initial = name.charAt(0).toUpperCase();

  if (url && !imgError) {
    return (
      <img
        src={url}
        alt={name}
        className="h-8 w-8 shrink-0 rounded-md object-contain"
        onError={() => setImgError(true)}
      />
    );
  }

  return (
    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-[var(--border-color)] text-sm font-semibold text-[var(--text-secondary)]">
      {initial}
    </div>
  );
}
