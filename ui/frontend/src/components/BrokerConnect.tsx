import React, { useState } from 'react';
import { connectBroker } from '../api';

export const BrokerConnect: React.FC = () => {
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

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

    return (
        <div className="section">
            <h3 className="section-title">Broker Connection</h3>
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
                    opacity: loading ? 0.7 : 1
                }}
            >
                {loading ? 'Connecting...' : 'Connect Broker'}
            </button>
            {error && (
                <div style={{ fontSize: '0.75rem', color: '#f85149', marginTop: '0.5rem' }}>
                    {error}
                </div>
            )}
        </div>
    );
};
