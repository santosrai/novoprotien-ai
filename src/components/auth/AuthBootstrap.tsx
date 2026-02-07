import React, { useEffect, useState, useRef } from 'react';
import axios from 'axios';
import { useAuthStore } from '../../stores/authStore';
import type { User } from '../../stores/authStore';

const AUTH_STORAGE_KEY = 'novoprotein-auth-storage';
const AUTH_TIMEOUT_MS = 10_000;
const baseURL = (import.meta as any).env?.VITE_API_BASE || 'http://localhost:8787/api';

function getStoredAuth(): { accessToken: string | null; refreshToken: string | null } {
  try {
    const raw = localStorage.getItem(AUTH_STORAGE_KEY);
    if (!raw) return { accessToken: null, refreshToken: null };
    const { state } = JSON.parse(raw);
    return {
      accessToken: state?.accessToken ?? null,
      refreshToken: state?.refreshToken ?? null,
    };
  } catch {
    return { accessToken: null, refreshToken: null };
  }
}

function clearStoredAuth(): void {
  try {
    localStorage.removeItem(AUTH_STORAGE_KEY);
  } catch {
    /* ignore */
  }
}

function withTimeout<T>(promise: Promise<T>, ms: number): Promise<T> {
  return Promise.race([
    promise,
    new Promise<T>((_, reject) =>
      setTimeout(() => reject(new Error('Auth validation timeout')), ms)
    ),
  ]);
}

interface AuthBootstrapProps {
  children: React.ReactNode;
}

/**
 * Validates auth before rendering protected content.
 * - No token: render children immediately.
 * - Token exists: show full-screen spinner, validate via GET /api/auth/me,
 *   refresh if 401, then render children. Timeout after 10s.
 */
export const AuthBootstrap: React.FC<AuthBootstrapProps> = ({ children }) => {
  const [validating, setValidating] = useState(true);
  const ranRef = useRef(false);
  const { setAuthFromBootstrap, setAuthResolved } = useAuthStore();

  useEffect(() => {
    if (ranRef.current) return;
    ranRef.current = true;

    const { accessToken, refreshToken } = getStoredAuth();

    if (!accessToken && !refreshToken) {
      setAuthFromBootstrap({
        user: null,
        accessToken: null,
        refreshToken: null,
        isAuthenticated: false,
      });
      setAuthResolved(true);
      setValidating(false);
      return;
    }

    const validate = async () => {
      let currentToken = accessToken;

      // If we only have refresh token, try refresh first
      if (!currentToken && refreshToken) {
        try {
          const refreshRes = await withTimeout(
            axios.post<{ access_token?: string }>(`${baseURL}/auth/refresh`, {
              refresh_token: refreshToken,
            }),
            AUTH_TIMEOUT_MS
          );
          if (refreshRes.status === 200 && refreshRes.data.access_token) {
            currentToken = refreshRes.data.access_token;
            try {
              const raw = localStorage.getItem(AUTH_STORAGE_KEY);
              if (raw) {
                const parsed = JSON.parse(raw);
                const updated = { ...parsed.state, accessToken: currentToken };
                localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify({ state: updated }));
              }
            } catch {
              /* ignore */
            }
          }
        } catch {
          /* fall through to clear auth */
        }
      }

      if (!currentToken) {
        clearStoredAuth();
        setAuthFromBootstrap({
          user: null,
          accessToken: null,
          refreshToken: null,
          isAuthenticated: false,
        });
        setAuthResolved(true);
        setValidating(false);
        return;
      }

      const headers: Record<string, string> = {
        Authorization: `Bearer ${currentToken}`,
      };

      try {
        const res = await withTimeout(
          axios.get<{ status: string; user: User }>(`${baseURL}/auth/me`, {
            headers,
            validateStatus: (s) => s < 500,
          }),
          AUTH_TIMEOUT_MS
        );

        if (res.status === 200 && res.data.status === 'success' && res.data.user) {
          const stored = getStoredAuth();
          setAuthFromBootstrap({
            user: res.data.user,
            accessToken: stored.accessToken,
            refreshToken: stored.refreshToken,
            isAuthenticated: true,
          });
          setAuthResolved(true);
          setValidating(false);
          return;
        }

        if (res.status === 401 && refreshToken) {
          const refreshRes = await withTimeout(
            axios.post<{ access_token?: string }>(`${baseURL}/auth/refresh`, {
              refresh_token: refreshToken,
            }),
            AUTH_TIMEOUT_MS
          );

          if (refreshRes.status === 200 && refreshRes.data.access_token) {
            const newToken = refreshRes.data.access_token;
            try {
              const raw = localStorage.getItem(AUTH_STORAGE_KEY);
              if (raw) {
                const parsed = JSON.parse(raw);
                const updated = { ...parsed.state, accessToken: newToken };
                localStorage.setItem(
                  AUTH_STORAGE_KEY,
                  JSON.stringify({ state: updated })
                );
              }
            } catch {
              /* ignore */
            }

            const meRes = await withTimeout(
              axios.get<{ status: string; user: User }>(`${baseURL}/auth/me`, {
                headers: { Authorization: `Bearer ${newToken}` },
                validateStatus: (s) => s < 500,
              }),
              AUTH_TIMEOUT_MS
            );

            if (meRes.status === 200 && meRes.data.status === 'success' && meRes.data.user) {
              const stored = getStoredAuth();
              setAuthFromBootstrap({
                user: meRes.data.user,
                accessToken: stored.accessToken,
                refreshToken: stored.refreshToken,
                isAuthenticated: true,
              });
              setAuthResolved(true);
              setValidating(false);
              return;
            }
          }
        }

        clearStoredAuth();
        setAuthFromBootstrap({
          user: null,
          accessToken: null,
          refreshToken: null,
          isAuthenticated: false,
        });
      } catch {
        clearStoredAuth();
        setAuthFromBootstrap({
          user: null,
          accessToken: null,
          refreshToken: null,
          isAuthenticated: false,
        });
      }

      setAuthResolved(true);
      setValidating(false);
    };

    validate();
  }, [setAuthFromBootstrap, setAuthResolved]);

  if (validating) {
    return (
      <div
        className="fixed inset-0 flex flex-col items-center justify-center bg-app text-app"
        data-testid="auth-bootstrap-spinner"
      >
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-current mb-4" />
        <p className="text-sm opacity-80">Verifying session...</p>
      </div>
    );
  }

  return <>{children}</>;
};
