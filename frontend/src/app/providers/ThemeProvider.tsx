import { useEffect, useMemo, useState, type ReactNode } from "react";

import {
  ThemeProviderContext,
  type ResolvedTheme,
  type Theme,
  type ThemeProviderState,
} from "@/app/providers/theme-context";

interface ThemeProviderProps {
  children: ReactNode;
  defaultTheme?: Theme;
  storageKey?: string;
}

function getSystemTheme(): ResolvedTheme {
  if (typeof window === "undefined") return "light";
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function applyThemeClass(resolvedTheme: ResolvedTheme): void {
  const root = window.document.documentElement;
  root.classList.remove("light", "dark");
  root.classList.add(resolvedTheme);
}

/**
 * Light/Dark/System theme provider. Hand-rolled rather than pulling in
 * `next-themes` (that package is Next.js-specific) — this is the same
 * "persist to storage + toggle a class on <html>" mechanism, sized for a
 * plain Vite SPA. Tailwind's `darkMode: ["class"]` (tailwind.config.ts) is
 * what actually makes the `.dark` class switch every CSS-variable-backed
 * color (src/index.css). The `useTheme` hook consuming this provider's
 * context lives in its own file (app/providers/useTheme.ts) — see
 * theme-context.ts's docstring for why.
 */
export function ThemeProvider({
  children,
  defaultTheme = "system",
  storageKey = "united-hrms-theme",
}: ThemeProviderProps) {
  const [theme, setThemeState] = useState<Theme>(() => {
    if (typeof window === "undefined") return defaultTheme;
    const stored = localStorage.getItem(storageKey) as Theme | null;
    return stored ?? defaultTheme;
  });

  const [resolvedTheme, setResolvedTheme] = useState<ResolvedTheme>(() =>
    theme === "system" ? getSystemTheme() : theme,
  );

  useEffect(() => {
    const next = theme === "system" ? getSystemTheme() : theme;
    setResolvedTheme(next);
    applyThemeClass(next);
  }, [theme]);

  useEffect(() => {
    if (theme !== "system") return undefined;

    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
    const handleChange = () => {
      const next = getSystemTheme();
      setResolvedTheme(next);
      applyThemeClass(next);
    };

    mediaQuery.addEventListener("change", handleChange);
    return () => mediaQuery.removeEventListener("change", handleChange);
  }, [theme]);

  const value = useMemo<ThemeProviderState>(
    () => ({
      theme,
      resolvedTheme,
      setTheme: (nextTheme: Theme) => {
        localStorage.setItem(storageKey, nextTheme);
        setThemeState(nextTheme);
      },
    }),
    [theme, resolvedTheme, storageKey],
  );

  return <ThemeProviderContext.Provider value={value}>{children}</ThemeProviderContext.Provider>;
}
