import React, { useEffect, useState } from 'react';
import { fetchTrades, syncBroker, Trade } from '../api';

export const TradeHistoryTable: React.FC = () => {
    const [trades, setTrades] = useState<Trade[]>([]);
    const [loading, setLoading] = useState(false);
    const [syncing, setSyncing] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const loadTrades = async () => {
        setLoading(true);
        try {
            const data = await fetchTrades();
            setTrades(data);
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : 'Failed to fetch trades');
        } finally {
            setLoading(false);
        }
    };

    const handleSync = async () => {
        setSyncing(true);
        try {
            await syncBroker();
            await loadTrades();
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : 'Sync failed');
        } finally {
            setSyncing(false);
        }
    };

    useEffect(() => {
        loadTrades();
    }, []);

    return (
        <div className="section">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                <h3 className="section-title" style={{ margin: 0 }}>Trade History</h3>
                <button
                    onClick={handleSync}
                    disabled={syncing}
                    style={{
                        padding: '0.5rem 1rem',
                        backgroundColor: '#1f6feb',
                        color: '#fff',
                        border: 'none',
                        borderRadius: '6px',
                        cursor: syncing ? 'not-allowed' : 'pointer',
                        fontSize: '0.85rem'
                    }}
                >
                    {syncing ? 'Syncing...' : 'Sync Trades'}
                </button>
            </div>

            {error && <div className="error" style={{ marginBottom: '1rem' }}>{error}</div>}

            {loading ? (
                <div className="loading">Loading trades...</div>
            ) : trades.length === 0 ? (
                <div style={{ color: '#8b949e', fontStyle: 'italic' }}>No trades found. Connect a broker and sync.</div>
            ) : (
                <div style={{ maxHeight: '400px', overflow: 'auto' }}>
                    <table className="table" style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
                        <thead style={{ background: '#161b22', position: 'sticky', top: 0 }}>
                            <tr>
                                <th style={{ padding: '0.5rem', textAlign: 'left' }}>Date</th>
                                <th style={{ padding: '0.5rem', textAlign: 'left' }}>Symbol</th>
                                <th style={{ padding: '0.5rem', textAlign: 'left' }}>Side</th>
                                <th style={{ padding: '0.5rem', textAlign: 'right' }}>Qty</th>
                                <th style={{ padding: '0.5rem', textAlign: 'right' }}>Price</th>
                                <th style={{ padding: '0.5rem', textAlign: 'left' }}>Broker</th>
                            </tr>
                        </thead>
                        <tbody>
                            {trades.map((trade, idx) => (
                                <tr key={idx} style={{ borderBottom: '1px solid #30363d' }}>
                                    <td style={{ padding: '0.5rem' }}>{new Date(trade.executed_at).toLocaleDateString()}</td>
                                    <td style={{ padding: '0.5rem' }}>{trade.symbol}</td>
                                    <td style={{ padding: '0.5rem', color: trade.side.toLowerCase() === 'buy' ? '#3fb950' : '#f85149' }}>
                                        {trade.side.toUpperCase()}
                                    </td>
                                    <td style={{ padding: '0.5rem', textAlign: 'right' }}>{trade.quantity}</td>
                                    <td style={{ padding: '0.5rem', textAlign: 'right' }}>${trade.price.toFixed(2)}</td>
                                    <td style={{ padding: '0.5rem' }}>{trade.brokerage}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
};
