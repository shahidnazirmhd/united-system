import { createContext } from "react";

export interface AuthTokenPair {
  accessToken: string;
  refreshToken: string;
}

export interface AuthContextState {
  /** Whether a valid (present, unexpired) session currently exists. */
  isAuthenticated: boolean;
  /** Stores a fresh token pair and marks the session as authenticated. */
  login: (tokens: AuthTokenPair) => void;
  /** Clears the stored session. Does not call the backend — see useSignOut for that. */
  logout: () => void;
}

/**
 * Split out from AuthProvider.tsx/useAuth.ts deliberately — the same reason
 * app/providers/theme-context.ts is split from ThemeProvider.tsx/useTheme.ts:
 * a file exporting both a component and a hook trips
 * `react-refresh/only-export-components`.
 */
export const AuthContext = createContext<AuthContextState | undefined>(undefined);
