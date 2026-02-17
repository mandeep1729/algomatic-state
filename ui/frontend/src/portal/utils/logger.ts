/**
 * Lightweight structured logger for the portal frontend.
 *
 * Creates namespaced loggers that output via console.debug/info/warn/error
 * with a consistent "[namespace]" prefix for easy filtering in DevTools.
 *
 * Debug-level logging is suppressed in production builds unless
 * localStorage.debug is set to "true" or "*".
 *
 * Usage:
 *   import { createLogger } from '../utils/logger';
 *   const log = createLogger('AuthContext');
 *   log.debug('Validating token');
 *   log.info('User logged in', { userId: 42 });
 *   log.warn('Token near expiry');
 *   log.error('Login failed', err);
 */

function isDebugEnabled(): boolean {
  try {
    const flag = localStorage.getItem('debug');
    return flag === 'true' || flag === '*';
  } catch {
    return false;
  }
}

const isDev = import.meta.env.MODE === 'development';

export interface Logger {
  debug: (...args: unknown[]) => void;
  info: (...args: unknown[]) => void;
  warn: (...args: unknown[]) => void;
  error: (...args: unknown[]) => void;
}

export function createLogger(namespace: string): Logger {
  const prefix = `[${namespace}]`;

  return {
    debug(...args: unknown[]) {
      if (isDev || isDebugEnabled()) {
        console.debug(prefix, ...args);
      }
    },
    info(...args: unknown[]) {
      console.info(prefix, ...args);
    },
    warn(...args: unknown[]) {
      console.warn(prefix, ...args);
    },
    error(...args: unknown[]) {
      console.error(prefix, ...args);
    },
  };
}
