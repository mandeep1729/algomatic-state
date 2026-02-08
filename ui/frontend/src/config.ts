/**
 * Frontend configuration loaded from environment variables.
 *
 * Vite requires env vars to be prefixed with VITE_ to be exposed to the client.
 * These are baked in at build time.
 *
 * For local development:
 *   - Create ui/frontend/.env.local with your overrides
 *   - Or rely on Vite proxy (default behavior when VITE_API_URL is not set)
 *
 * For Vercel deployment:
 *   - Set VITE_API_URL in Vercel Project Settings > Environment Variables
 *   - Example: https://api.yourdomain.com
 *
 * Environment variable reference:
 *   VITE_API_URL          - Backend API base URL (e.g., https://api.example.com)
 *                           If not set, uses relative URLs with Vite proxy in dev
 *   VITE_GOOGLE_CLIENT_ID - Google OAuth client ID for authentication
 *   VITE_USE_MOCKS        - Set to "true" to use mock data instead of real API
 */

interface Config {
  /**
   * Backend API base URL.
   * - In development: empty string (uses Vite proxy at /api)
   * - In production: full URL like "https://api.yourdomain.com"
   */
  apiUrl: string;

  /**
   * Google OAuth client ID for authentication.
   */
  googleClientId: string;

  /**
   * Whether to use mock data instead of real API calls.
   */
  useMocks: boolean;

  /**
   * Current environment.
   */
  isDevelopment: boolean;
  isProduction: boolean;
}

function loadConfig(): Config {
  const apiUrl = import.meta.env.VITE_API_URL || '';
  const googleClientId = import.meta.env.VITE_GOOGLE_CLIENT_ID || '';
  const useMocks = import.meta.env.VITE_USE_MOCKS === 'true';
  const mode = import.meta.env.MODE;

  return {
    apiUrl: apiUrl.replace(/\/$/, ''), // Remove trailing slash if present
    googleClientId,
    useMocks,
    isDevelopment: mode === 'development',
    isProduction: mode === 'production',
  };
}

export const config = loadConfig();

/**
 * Build a full API URL from a path.
 *
 * @param path - API path starting with /api (e.g., "/api/auth/me")
 * @returns Full URL in production, relative path in development
 *
 * @example
 * // Development (VITE_API_URL not set):
 * apiUrl("/api/auth/me") // => "/api/auth/me"
 *
 * // Production (VITE_API_URL="https://api.example.com"):
 * apiUrl("/api/auth/me") // => "https://api.example.com/api/auth/me"
 */
export function apiUrl(path: string): string {
  if (config.apiUrl) {
    return `${config.apiUrl}${path}`;
  }
  return path;
}
