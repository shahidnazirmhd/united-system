import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";

import { clearTokenPair, hasValidAccessToken, setTokenPair } from "@/lib/api/authToken";
import { AuthContext, type AuthContextState, type AuthTokenPair } from "@/lib/auth/auth-context";
import { subscribeToSessionExpired } from "@/lib/auth/sessionEvents";

interface AuthProviderProps {
  children: ReactNode;
}

/**
 * Owns the one piece of state the rest of the app needs about
 * authentication: whether a valid session currently exists. Deliberately
 * thin — it does not fetch a user profile and does not know about routes or
 * the backend's specific endpoints (`modules/auth`'s login flow and
 * `useSignOut` own those calls). Its only jobs are: (a) initialize from
 * whatever token is already in storage when the app loads, (b) expose
 * `login`/`logout` so storage and this state always change together, and
 * (c) react to `sessionEvents` firing when httpClient's silent token refresh
 * fails, so every consumer (ProtectedRoute, PublicOnlyRoute, a future
 * profile menu) updates immediately instead of staying stale until the next
 * manual navigation.
 */
export function AuthProvider({ children }: AuthProviderProps) {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(() => hasValidAccessToken());

  useEffect(() => subscribeToSessionExpired(() => setIsAuthenticated(false)), []);

  const login = useCallback((tokens: AuthTokenPair) => {
    setTokenPair(tokens.accessToken, tokens.refreshToken);
    setIsAuthenticated(true);
  }, []);

  const logout = useCallback(() => {
    clearTokenPair();
    setIsAuthenticated(false);
  }, []);

  const value = useMemo<AuthContextState>(
    () => ({ isAuthenticated, login, logout }),
    [isAuthenticated, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
