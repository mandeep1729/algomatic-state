import { Outlet, Link } from 'react-router-dom';
import { Shield, ArrowRight } from 'lucide-react';

export default function PublicLayout() {
  return (
    <div className="min-h-screen bg-[var(--bg-primary)] text-[var(--text-primary)]">
      {/* Header */}
      <header className="border-b border-[var(--border-color)] bg-[var(--bg-secondary)]">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <Link to="/" className="flex items-center gap-2 text-lg font-semibold">
            <Shield size={20} className="text-[var(--accent-blue)]" />
            Trading Buddy
          </Link>
          <nav className="flex items-center gap-6 text-sm">
            <Link to="/how-it-works" className="text-[var(--text-secondary)] transition-colors duration-150 hover:text-[var(--text-primary)]">
              How It Works
            </Link>
            <Link to="/what-we-evaluate" className="text-[var(--text-secondary)] transition-colors duration-150 hover:text-[var(--text-primary)]">
              What We Evaluate
            </Link>
            <Link to="/pricing" className="text-[var(--text-secondary)] transition-colors duration-150 hover:text-[var(--text-primary)]">
              Pricing
            </Link>
            <Link to="/faq" className="text-[var(--text-secondary)] transition-colors duration-150 hover:text-[var(--text-primary)]">
              FAQ
            </Link>
            <Link
              to="/app"
              className="flex items-center gap-1.5 rounded-md bg-[var(--accent-blue)] px-4 py-1.5 text-white transition-opacity duration-150 hover:opacity-90"
            >
              Open App
              <ArrowRight size={14} />
            </Link>
          </nav>
        </div>
      </header>

      {/* Main content */}
      <main className="mx-auto max-w-6xl px-6 py-8">
        <Outlet />
      </main>

      {/* Footer */}
      <footer className="border-t border-[var(--border-color)] bg-[var(--bg-secondary)]">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4 text-xs text-[var(--text-secondary)]">
          <span className="flex items-center gap-1.5">
            <Shield size={12} className="text-[var(--accent-blue)]" />
            Trading Buddy — Not a signal service
          </span>
          <div className="flex gap-4">
            <Link to="/legal/disclaimer" className="transition-colors duration-150 hover:text-[var(--text-primary)]">Disclaimer</Link>
            <Link to="/legal/terms" className="transition-colors duration-150 hover:text-[var(--text-primary)]">Terms</Link>
            <Link to="/legal/privacy" className="transition-colors duration-150 hover:text-[var(--text-primary)]">Privacy</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
