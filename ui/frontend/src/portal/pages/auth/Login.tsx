import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { GoogleLogin } from '@react-oauth/google';
import { useAuth, WaitlistError } from '../../context/AuthContext';
import { Shield, Clock } from 'lucide-react';

export default function Login() {
  const { user, login, loading } = useAuth();
  const navigate = useNavigate();
  const [waitlistMessage, setWaitlistMessage] = useState<string | null>(null);

  // If already authenticated, redirect to app
  useEffect(() => {
    if (user && !loading) {
      navigate('/app', { replace: true });
    }
  }, [user, loading, navigate]);

  async function handleGoogleSuccess(credentialResponse: { credential?: string }) {
    if (!credentialResponse.credential) return;
    setWaitlistMessage(null);
    try {
      await login(credentialResponse.credential);
      navigate('/app', { replace: true });
    } catch (err) {
      if (err instanceof WaitlistError) {
        setWaitlistMessage(err.detail);
      } else {
        console.error('Login failed:', err);
      }
    }
  }

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-[var(--bg-primary)]">
        <div className="text-[var(--text-secondary)]">Loading...</div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--bg-primary)] px-4">
      <div className="w-full max-w-sm space-y-8">
        {/* Logo / brand */}
        <div className="text-center">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-[var(--accent-blue)]/10 text-[var(--accent-blue)]">
            <Shield size={24} />
          </div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">Trading Buddy</h1>
          <p className="mt-2 text-sm text-[var(--text-secondary)]">
            Sign in to access your trading copilot
          </p>
        </div>

        {/* Waitlist pending message */}
        {waitlistMessage && (
          <div className="rounded-xl border border-yellow-500/30 bg-yellow-500/10 p-6 text-center">
            <div className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-yellow-500/20 text-yellow-500">
              <Clock size={20} />
            </div>
            <p className="text-sm font-medium text-[var(--text-primary)]">
              {waitlistMessage}
            </p>
            <Link
              to="/"
              className="mt-3 inline-block text-xs text-[var(--accent-blue)] hover:underline"
            >
              Back to homepage
            </Link>
          </div>
        )}

        {/* Sign-in card */}
        {!waitlistMessage && (
          <div className="rounded-xl border border-[var(--border-color)] bg-[var(--bg-secondary)] p-8">
            <div className="flex justify-center">
              <GoogleLogin
                onSuccess={handleGoogleSuccess}
                onError={() => console.error('Google login error')}
                shape="rectangular"
                size="large"
                text="signin_with"
                width="300"
              />
            </div>

            <p className="mt-6 text-center text-xs text-[var(--text-secondary)]">
              By signing in, you agree to our{' '}
              <a href="/legal/terms" className="underline hover:text-[var(--text-primary)]">
                Terms of Service
              </a>{' '}
              and{' '}
              <a href="/legal/privacy" className="underline hover:text-[var(--text-primary)]">
                Privacy Policy
              </a>
              .
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
