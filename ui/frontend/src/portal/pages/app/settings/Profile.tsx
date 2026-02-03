import { useEffect, useState } from 'react';
import api from '../../../api';
import type { TradingProfile } from '../../../types';

const EXPERIENCE_LEVELS = [
  { value: 'beginner', label: 'Beginner' },
  { value: 'intermediate', label: 'Intermediate' },
  { value: 'advanced', label: 'Advanced' },
] as const;

const TRADING_STYLES = [
  { value: 'day_trading', label: 'Day Trading' },
  { value: 'swing', label: 'Swing Trading' },
  { value: 'scalping', label: 'Scalping' },
  { value: 'position', label: 'Position Trading' },
] as const;

const MARKET_OPTIONS = ['US_EQUITIES', 'FOREX', 'CRYPTO', 'OPTIONS', 'FUTURES'];
const TIMEFRAME_OPTIONS = ['1Min', '5Min', '15Min', '1Hour', '4Hour', '1Day'];
const ACCOUNT_SIZES = ['< $1k', '$1k-$10k', '$10k-$50k', '$50k-$100k', '$100k+'];

export default function SettingsProfile() {
  const [profile, setProfile] = useState<TradingProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.fetchTradingProfile().then(setProfile).finally(() => setLoading(false));
  }, []);

  function updateField<K extends keyof TradingProfile>(key: K, value: TradingProfile[K]) {
    setProfile((prev) => prev ? { ...prev, [key]: value } : prev);
    setSaved(false);
  }

  function toggleArrayItem(key: 'primary_markets' | 'typical_timeframes', item: string) {
    setProfile((prev) => {
      if (!prev) return prev;
      const arr = prev[key];
      return { ...prev, [key]: arr.includes(item) ? arr.filter((v) => v !== item) : [...arr, item] };
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

  if (loading) return <div className="p-8 text-[var(--text-secondary)]">Loading...</div>;
  if (!profile) return null;

  return (
    <div className="p-6">
      <h1 className="mb-6 text-2xl font-semibold">Trading Profile</h1>

      <form onSubmit={handleSave} className="max-w-2xl space-y-6">
        <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-5 space-y-5">
          {/* Experience Level */}
          <FieldGroup label="Experience Level">
            <div className="flex gap-2">
              {EXPERIENCE_LEVELS.map((lvl) => (
                <button
                  key={lvl.value}
                  type="button"
                  onClick={() => updateField('experience_level', lvl.value)}
                  className={`flex-1 rounded-md border px-3 py-2 text-sm font-medium transition-colors ${
                    profile.experience_level === lvl.value
                      ? 'border-[var(--accent-blue)] bg-[var(--accent-blue)]/10 text-[var(--accent-blue)]'
                      : 'border-[var(--border-color)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
                  }`}
                >
                  {lvl.label}
                </button>
              ))}
            </div>
          </FieldGroup>

          {/* Trading Style */}
          <FieldGroup label="Trading Style">
            <div className="flex flex-wrap gap-2">
              {TRADING_STYLES.map((style) => (
                <button
                  key={style.value}
                  type="button"
                  onClick={() => updateField('trading_style', style.value)}
                  className={`rounded-md border px-3 py-2 text-sm font-medium transition-colors ${
                    profile.trading_style === style.value
                      ? 'border-[var(--accent-blue)] bg-[var(--accent-blue)]/10 text-[var(--accent-blue)]'
                      : 'border-[var(--border-color)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
                  }`}
                >
                  {style.label}
                </button>
              ))}
            </div>
          </FieldGroup>

          {/* Primary Markets */}
          <FieldGroup label="Primary Markets">
            <div className="flex flex-wrap gap-2">
              {MARKET_OPTIONS.map((market) => (
                <button
                  key={market}
                  type="button"
                  onClick={() => toggleArrayItem('primary_markets', market)}
                  className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
                    profile.primary_markets.includes(market)
                      ? 'border-[var(--accent-blue)] bg-[var(--accent-blue)]/10 text-[var(--accent-blue)]'
                      : 'border-[var(--border-color)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
                  }`}
                >
                  {market.replace(/_/g, ' ')}
                </button>
              ))}
            </div>
          </FieldGroup>

          {/* Typical Timeframes */}
          <FieldGroup label="Typical Timeframes">
            <div className="flex flex-wrap gap-2">
              {TIMEFRAME_OPTIONS.map((tf) => (
                <button
                  key={tf}
                  type="button"
                  onClick={() => toggleArrayItem('typical_timeframes', tf)}
                  className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
                    profile.typical_timeframes.includes(tf)
                      ? 'border-[var(--accent-blue)] bg-[var(--accent-blue)]/10 text-[var(--accent-blue)]'
                      : 'border-[var(--border-color)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
                  }`}
                >
                  {tf}
                </button>
              ))}
            </div>
          </FieldGroup>

          {/* Account Size */}
          <FieldGroup label="Account Size Range">
            <select
              value={profile.account_size_range}
              onChange={(e) => updateField('account_size_range', e.target.value)}
              className="form-input"
            >
              {ACCOUNT_SIZES.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </FieldGroup>
        </div>

        {/* Error / Success */}
        {error && (
          <div className="rounded-md border border-[var(--accent-red)] bg-[var(--accent-red)]/5 px-3 py-2 text-xs text-[var(--accent-red)]">
            {error}
          </div>
        )}
        {saved && (
          <div className="rounded-md border border-[var(--accent-green)] bg-[var(--accent-green)]/5 px-3 py-2 text-xs text-[var(--accent-green)]">
            Profile saved successfully.
          </div>
        )}

        <button
          type="submit"
          disabled={saving}
          className="rounded-md bg-[var(--accent-blue)] px-5 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {saving ? 'Saving...' : 'Save Profile'}
        </button>
      </form>
    </div>
  );
}

function FieldGroup({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="mb-2 block text-xs font-medium text-[var(--text-secondary)]">{label}</label>
      {children}
    </div>
  );
}
