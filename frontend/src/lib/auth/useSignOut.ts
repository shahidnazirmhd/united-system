import { useCallback } from "react";

import { API_ENDPOINTS } from "@/lib/api/endpoints";
import { getRefreshToken } from "@/lib/api/authToken";
import { httpClient } from "@/lib/api/httpClient";
import { useAuth } from "@/lib/auth/useAuth";

/**
 * Ends the current session: best-effort revokes the refresh token on the
 * server (IDENTITY_API.md's `POST /auth/logout/`), then always clears local
 * session state regardless of whether that call succeeded — if the token
 * was already invalid/expired, there is nothing left to revoke, but the user
 * still gets logged out locally. Deliberately does not navigate anywhere:
 * clearing local state flips `useAuth().isAuthenticated` to false, and
 * `ProtectedRoute` (an ancestor of every dashboard route) reacts to that on
 * its own by rendering a redirect to the login screen.
 */
export function useSignOut(): () => Promise<void> {
  const { logout } = useAuth();

  return useCallback(async () => {
    const refreshToken = getRefreshToken();
    if (refreshToken) {
      try {
        await httpClient.post(`${API_ENDPOINTS.auth}/logout/`, { refresh_token: refreshToken });
      } catch {
        // Best-effort only — local session state is cleared regardless.
      }
    }
    logout();
  }, [logout]);
}
