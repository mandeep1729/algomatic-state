import { useEffect, useState } from 'react';
import api from '../../../api';
import type { User } from '../../../types';
import { format } from 'date-fns';

export default function SettingsDataPrivacy() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.fetchCurrentUser().then(setUser).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="p-8 text-[var(--text-secondary)]">Loading...</div>;
  if (!user) return null;

  return (
    <div className="p-6">
      <h1 className="mb-6 text-2xl font-semibold">Data & Privacy</h1>

      <div className="max-w-2xl space-y-6">
        {/* Account info */}
        <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-5">
          <h2 className="mb-3 text-sm font-medium">Account Information</h2>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-[var(--text-secondary)]">Name</span>
              <span>{user.name}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-[var(--text-secondary)]">Email</span>
              <span>{user.email}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-[var(--text-secondary)]">Member since</span>
              <span>{format(new Date(user.created_at), 'MMMM d, yyyy')}</span>
            </div>
          </div>
        </div>

        {/* Data export */}
        <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-5">
          <h2 className="mb-3 text-sm font-medium">Export Your Data</h2>
          <p className="mb-4 text-xs text-[var(--text-secondary)]">
            Download all your data including trades, evaluations, journal entries, and settings.
          </p>
          <div className="flex gap-3">
            <button className="rounded-md border border-[var(--border-color)] px-4 py-2 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors">
              Export as JSON
            </button>
            <button className="rounded-md border border-[var(--border-color)] px-4 py-2 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors">
              Export as CSV
            </button>
          </div>
        </div>

        {/* Privacy */}
        <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-5">
          <h2 className="mb-3 text-sm font-medium">Privacy</h2>
          <div className="space-y-3 text-xs text-[var(--text-secondary)]">
            <p>
              Your trading data is stored securely and never shared with third parties.
              We do not sell your data or use it for advertising.
            </p>
            <p>
              Evaluations are processed using your data only. No personal information
              is used to train models.
            </p>
          </div>
        </div>

        {/* Danger zone */}
        <div className="rounded-lg border border-[var(--accent-red)]/30 bg-[var(--accent-red)]/5 p-5">
          <h2 className="mb-3 text-sm font-medium text-[var(--accent-red)]">Danger Zone</h2>
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-sm">Delete all trade data</div>
                <div className="text-xs text-[var(--text-secondary)]">Remove all trades, evaluations, and insights. This cannot be undone.</div>
              </div>
              <button className="rounded-md border border-[var(--accent-red)] px-3 py-1.5 text-xs font-medium text-[var(--accent-red)] hover:bg-[var(--accent-red)]/10 transition-colors">
                Delete Data
              </button>
            </div>
            <div className="flex items-center justify-between">
              <div>
                <div className="text-sm">Delete account</div>
                <div className="text-xs text-[var(--text-secondary)]">Permanently delete your account and all associated data.</div>
              </div>
              <button className="rounded-md border border-[var(--accent-red)] px-3 py-1.5 text-xs font-medium text-[var(--accent-red)] hover:bg-[var(--accent-red)]/10 transition-colors">
                Delete Account
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
