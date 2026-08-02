import { createContext } from "react";

export type Theme = "light" | "dark" | "system";
export type ResolvedTheme = "light" | "dark";

export interface ThemeProviderState {
  theme: Theme;
  resolvedTheme: ResolvedTheme;
  setTheme: (theme: Theme) => void;
}

/**
 * Split out from ThemeProvider.tsx/useTheme.ts deliberately — a file that
 * exports both a component and a hook trips
 * `react-refresh/only-export-components` (Fast Refresh can't reliably
 * preserve state across an edit to a file serving both roles). Keeping the
 * context itself in its own file, with no component or hook export, means
 * neither of the other two files has to make that trade-off.
 */
export const ThemeProviderContext = createContext<ThemeProviderState | undefined>(undefined);
