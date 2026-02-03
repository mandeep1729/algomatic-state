import { Outlet, Link } from 'react-router-dom';
import { Shield, ArrowRight } from 'lucide-react';

export default function PublicLayout() {
  return (
    <div className="flex min-h-screen flex-col bg-[var(--bg-primary)] text-[var(--text-primary)] font-sans antialiased selection:bg-[var(--accent-blue)] selection:text-white">
      {/* Header */}
      <header className="sticky top-0 z-50 w-full border-b border-[var(--border-color)] bg-[var(--bg-primary)]/80 backdrop-blur-md supports-[backdrop-filter]:bg-[var(--bg-primary)]/60">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6">
          <Link to="/" className="flex items-center gap-2.5 text-lg font-bold tracking-tight">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--accent-blue)]/10 text-[var(--accent-blue)]">
              <Shield size={20} strokeWidth={2.5} />
            </div>
            <span>Trading Buddy</span>
          </Link>

          <nav className="flex items-center gap-8 text-sm font-medium">
            <div className="hidden md:flex md:gap-8">
              <Link to="/how-it-works" className="text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)]">How It Works</Link>
              <Link to="/what-we-evaluate" className="text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)]">Features</Link>
              <Link to="/pricing" className="text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)]">Pricing</Link>
              <Link to="/faq" className="text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)]">FAQ</Link>
            </div>

            <Link
              to="/app"
              className="group flex items-center gap-2 rounded-full bg-[var(--text-primary)] px-5 py-2 text-sm font-semibold text-[var(--bg-primary)] transition-all hover:bg-[var(--text-primary)]/90 hover:shadow-lg hover:shadow-[var(--text-primary)]/20"
            >
              Open App
              <ArrowRight size={16} className="transition-transform group-hover:translate-x-0.5" />
            </Link>
          </nav>
        </div>
      </header>

      {/* Main content */}
      <main className="flex-1">
        <div className="mx-auto max-w-7xl px-6 py-12 lg:py-16">
          <Outlet />
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-[var(--border-color)] bg-[var(--bg-secondary)]/50 py-12">
        <div className="mx-auto flex max-w-7xl flex-col gap-8 px-6 md:flex-row md:items-center md:justify-between">
          <div className="flex flex-col gap-2">
            <span className="flex items-center gap-2 text-sm font-semibold">
              <Shield size={16} className="text-[var(--accent-blue)]" />
              Trading Buddy
            </span>
            <p className="text-xs text-[var(--text-secondary)]">
              &copy; {new Date().getFullYear()} Algomatic. Built for disciplined traders.
            </p>
          </div>

          <div className="flex gap-8 text-sm text-[var(--text-secondary)]">
            <Link to="/legal/disclaimer" className="hover:text-[var(--text-primary)]">Disclaimer</Link>
            <Link to="/legal/terms" className="hover:text-[var(--text-primary)]">Terms</Link>
            <Link to="/legal/privacy" className="hover:text-[var(--text-primary)]">Privacy</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
