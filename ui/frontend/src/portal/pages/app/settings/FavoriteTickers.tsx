import { useEffect, useState } from 'react';
import { X } from 'lucide-react';
import api from '../../../api';
import type { TradingProfile } from '../../../types';

export default function SettingsFavoriteTickers() {
  const [profile, setProfile] = useState<TradingProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [inputValue, setInputValue] = useState('');

  useEffect(() => {
    api.fetchTradingProfile().then(setProfile).finally(() => setLoading(false));
  }, []);

  function addTicker() {
    const ticker = inputValue.trim().toUpperCase();
    if (!ticker) return;
    if (!profile) return;

    const currentTickers = profile.favorite_tickers || [];
    if (currentTickers.includes(ticker)) {
      setError('Ticker already added');
      return;
    }

    setProfile({
      ...profile,
      favorite_tickers: [...currentTickers, ticker],
    });
    setInputValue('');
    setError(null);
    setSaved(false);
  }

  function removeTicker(ticker: string) {
    if (!profile) return;
    setProfile({
      ...profile,
      favorite_tickers: (profile.favorite_tickers || []).filter((t) => t !== ticker),
    });
    setSaved(false);
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!profile) return;
    setError(null);
    setSaving(true);
    try {
      const updated = await api.updateTradingProfile(profile);
      setProfile(updated);
      setSaved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save');
    } finally {
      setSaving(false);
    }
  }

  function handleInputKeyPress(e: React.KeyboardEvent) {
    if (e.key === 'Enter') {
      e.preventDefault();
      addTicker();
    }
  }

  if (loading) return <div className="p-8 text-[var(--text-secondary)]">Loading...</div>;
  if (!profile) return null;

  const tickers = profile.favorite_tickers || [];

  return (
    <div className="p-6">
      <h1 className="mb-2 text-2xl font-semibold">Favorite Tickers</h1>
      <p className="mb-6 text-sm text-[var(--text-secondary)]">
        Add tickers you frequently trade to access them quickly.
      </p>

      <form onSubmit={handleSave} className="max-w-2xl space-y-6">
        <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-5 space-y-5">
          <div>
            <label className="mb-3 block text-xs font-medium text-[var(--text-secondary)]">Add Ticker</label>
            <div className="flex gap-2">
              <input
                type="text"
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyPress={handleInputKeyPress}
                placeholder="Enter ticker symbol (e.g., AAPL, TSLA)"
                className="flex-1 rounded-md border border-[var(--border-color)] bg-[var(--bg-primary)] px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-secondary)] focus:border-[var(--accent-blue)] focus:outline-none focus:ring-1 focus:ring-[var(--accent-blue)]"
              />
              <button
                type="button"
                onClick={addTicker}
                className="rounded-md bg-[var(--accent-blue)] px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
              >
                Add
              </button>
            </div>
          </div>

          {tickers.length > 0 && (
            <div>
              <label className="mb-3 block text-xs font-medium text-[var(--text-secondary)]">Your Favorite Tickers</label>
              <div className="flex flex-wrap gap-2">
                {tickers.map((ticker) => (
                  <div
                    key={ticker}
                    className="flex items-center gap-2 rounded-full bg-[var(--accent-blue)]/10 px-3 py-1.5 text-sm font-medium text-[var(--accent-blue)] border border-[var(--accent-blue)]/30"
                  >
                    {ticker}
                    <button
                      type="button"
                      onClick={() => removeTicker(ticker)}
                      className="flex items-center justify-center rounded-full hover:bg-[var(--accent-blue)]/20 transition-colors"
                      title="Remove ticker"
                    >
                      <X size={14} />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {tickers.length === 0 && (
            <div className="rounded-md bg-[var(--bg-tertiary)] px-3 py-3 text-xs text-[var(--text-secondary)]">
              No favorite tickers yet. Add your first ticker above.
            </div>
          )}
        </div>

        {/* Error / Success */}
        {error && (
          <div className="rounded-md border border-[var(--accent-red)] bg-[var(--accent-red)]/5 px-3 py-2 text-xs text-[var(--accent-red)]">
            {error}
          </div>
        )}
        {saved && (
          <div className="rounded-md border border-[var(--accent-green)] bg-[var(--accent-green)]/5 px-3 py-2 text-xs text-[var(--accent-green)]">
            Favorite tickers saved successfully.
          </div>
        )}

        <button
          type="submit"
          disabled={saving}
          className="rounded-md bg-[var(--accent-blue)] px-5 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {saving ? 'Saving...' : 'Save Tickers'}
        </button>
      </form>
    </div>
  );
}
