import React, { useState, useEffect } from 'react';
import { connectBroker, fetchBrokerStatus, syncBroker } from '../api';
import type { BrokerStatus } from '../api';

export const BrokerConnect: React.FC = () => {
    const [loading, setLoading] = useState(false);
    const [syncing, setSyncing] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [status, setStatus] = useState<BrokerStatus | null>(null);

    // Fetch broker status on mount
    useEffect(() => {
        fetchBrokerStatus()
            .then(setStatus)
            .catch((err) => console.warn('Failed to fetch broker status:', err));
    }, []);

    const handleConnect = async () => {
        setLoading(true);
        setError(null);
        try {
            const response = await connectBroker();
            if (response.redirect_url) {
                window.location.href = response.redirect_url;
            } else {
                setError("No redirect URL received");
            }
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : 'Failed to initiate connection');
        } finally {
            setLoading(false);
        }
    };

    const handleSync = async () => {
        setSyncing(true);
        setError(null);
        try {
            const response = await syncBroker();
            // Refresh status after sync
            const newStatus = await fetchBrokerStatus();
            setStatus(newStatus);
            if (response.trades_synced > 0) {
                setError(null);
            }
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : 'Failed to sync');
        } finally {
            setSyncing(false);
        }
    };

    return (
        <div className="section">
            <h3 className="section-title">Broker Connections</h3>

            {/* Connected Brokers List */}
            {status && status.connected && status.brokerages.length > 0 && (
                <div style={{
                    marginBottom: '0.75rem',
                    padding: '0.5rem',
                    backgroundColor: '#0d1117',
                    borderRadius: '6px',
                    border: '1px solid #238636',
                }}>
                    <div style={{ fontSize: '0.75rem', color: '#3fb950', marginBottom: '0.25rem' }}>
                        Connected
                    </div>
                    {status.brokerages.map((broker, idx) => (
                        <div key={idx} style={{
                            fontSize: '0.875rem',
                            color: '#e6edf3',
                            padding: '0.25rem 0',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '0.5rem',
                        }}>
                            <span style={{ color: '#3fb950' }}>●</span>
                            {broker}
                        </div>
                    ))}
                </div>
            )}

            {/* Connect Button */}
            <button
                onClick={handleConnect}
                disabled={loading}
                style={{
                    width: '100%',
                    padding: '0.75rem 1rem',
                    backgroundColor: '#238636',
                    color: '#fff',
                    border: 'none',
                    borderRadius: '6px',
                    cursor: loading ? 'not-allowed' : 'pointer',
                    opacity: loading ? 0.7 : 1,
                    marginBottom: '0.5rem',
                }}
            >
                {loading ? 'Connecting...' : 'Add Broker Connection'}
            </button>

            {/* Sync Button - show only if connected */}
            {status?.connected && (
                <button
                    onClick={handleSync}
                    disabled={syncing}
                    style={{
                        width: '100%',
                        padding: '0.5rem 1rem',
                        backgroundColor: '#21262d',
                        color: '#e6edf3',
                        border: '1px solid #30363d',
                        borderRadius: '6px',
                        cursor: syncing ? 'not-allowed' : 'pointer',
                        opacity: syncing ? 0.7 : 1,
                        fontSize: '0.875rem',
                    }}
                >
                    {syncing ? 'Syncing...' : 'Sync Trades'}
                </button>
            )}

            {error && (
                <div style={{ fontSize: '0.75rem', color: '#f85149', marginTop: '0.5rem' }}>
                    {error}
                </div>
            )}
        </div>
    );
};
