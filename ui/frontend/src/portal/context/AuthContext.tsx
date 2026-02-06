import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react';

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
  // In dev mode (AUTH_DEV_MODE=true), backend returns user without token
  useEffect(() => {
    let cancelled = false;

    async function fetchMe() {
      try {
        // First try without token (works if backend has AUTH_DEV_MODE=true)
        let res = await fetch('/api/auth/me');

        // If unauthorized and we have a token, try with it
        if (res.status === 401 && token) {
          res = await fetch('/api/auth/me', {
            headers: { Authorization: `Bearer ${token}` },
          });
        }

        if (!res.ok) {
          // Token invalid/expired or no auth — clear it
          localStorage.removeItem(TOKEN_KEY);
          setToken(null);
          setUser(null);
        } else {
          const data = await res.json();
          if (!cancelled) setUser(data);
        }
      } catch {
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
    const res = await fetch('/api/auth/google', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ credential }),
    });

    if (!res.ok) {
      const body = await res.text().catch(() => '');
      throw new Error(`Login failed: ${body || res.statusText}`);
    }

    const data = await res.json();
    localStorage.setItem(TOKEN_KEY, data.access_token);
    setToken(data.access_token);
    setUser(data.user);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setUser(null);
    // Fire-and-forget server logout
    fetch('/api/auth/logout', { method: 'POST' }).catch(() => {});
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
