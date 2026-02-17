import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react';
import { apiUrl } from '../../config';
import { createLogger } from '../utils/logger';

const log = createLogger('AuthContext');

/** Thrown when the backend returns 403 — user is not yet approved. */
export class WaitlistError extends Error {
  constructor(public detail: string) {
    super(detail);
    this.name = 'WaitlistError';
  }
}

interface AuthUser {
  id: number;
  name: string;
  email: string;
  profile_picture_url?: string | null;
  auth_provider: string;
}

interface AuthContextValue {
  user: AuthUser | null;
  token: string | null;
  loading: boolean;
  login: (credential: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

const TOKEN_KEY = 'auth_token';

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(TOKEN_KEY));
  const [loading, setLoading] = useState(true);

  // On mount (or token change), validate authentication by calling /api/auth/me
  useEffect(() => {
    let cancelled = false;

    async function fetchMe() {
      log.debug('Validating session via /api/auth/me');
      try {
        const headers: Record<string, string> = {};
        if (token) {
          headers['Authorization'] = `Bearer ${token}`;
        }

        const res = await fetch(apiUrl('/api/auth/me'), { headers });

        if (!res.ok) {
          // Token invalid/expired or no auth — clear it
          log.info('Session validation failed (status %d), clearing token', res.status);
          localStorage.removeItem(TOKEN_KEY);
          setToken(null);
          setUser(null);
        } else {
          const data = await res.json();
          if (!cancelled) {
            log.info('Session validated for user_id=%d', data.id);
            setUser(data);
          }
        }
      } catch (err) {
        log.error('Session validation error, clearing token', err);
        localStorage.removeItem(TOKEN_KEY);
        setToken(null);
        setUser(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetchMe();
    return () => { cancelled = true; };
  }, [token]);

  const login = useCallback(async (credential: string) => {
    log.debug('Starting Google OAuth login');
    const res = await fetch(apiUrl('/api/auth/google'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ credential }),
    });

    if (res.status === 403) {
      const body = await res.json().catch(() => ({ detail: 'Account pending approval' }));
      log.warn('Login blocked by waitlist: %s', body.detail);
      throw new WaitlistError(body.detail || 'Account pending approval');
    }

    if (!res.ok) {
      const body = await res.text().catch(() => '');
      log.error('Login failed with status %d: %s', res.status, body || res.statusText);
      throw new Error(`Login failed: ${body || res.statusText}`);
    }

    const data = await res.json();
    log.info('Login successful for user_id=%d', data.user?.id);
    localStorage.setItem(TOKEN_KEY, data.access_token);
    setToken(data.access_token);
    setUser(data.user);
  }, []);

  const logout = useCallback(() => {
    log.info('User logging out');
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setUser(null);
    // Fire-and-forget server logout
    fetch(apiUrl('/api/auth/logout'), { method: 'POST' }).catch(() => {});
  }, []);

  return (
    <AuthContext.Provider value={{ user, token, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider');
  return ctx;
}
