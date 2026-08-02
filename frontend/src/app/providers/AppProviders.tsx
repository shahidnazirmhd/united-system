import type { ReactNode } from "react";

import { ErrorBoundary } from "@/app/error/ErrorBoundary";
import { GlobalErrorFallback } from "@/app/error/GlobalErrorFallback";
import { QueryProvider } from "@/app/providers/QueryProvider";
import { ThemeProvider } from "@/app/providers/ThemeProvider";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { AuthProvider } from "@/lib/auth";

interface AppProvidersProps {
  children: ReactNode;
}

/**
 * Single composition root for every cross-cutting concern the application
 * needs, nested in the order they must be. `AuthProvider` lives in
 * `lib/auth` (foundation), not here, since it's also depended on by
 * `app/router`'s route guards and by `src/modules/auth` — this is just
 * where it gets mounted. Adding a new global concern later (an i18n
 * provider, a feature-flag provider) means adding exactly one line here —
 * no other file in the app should ever import a provider directly.
 */
export function AppProviders({ children }: AppProvidersProps) {
  return (
    <ErrorBoundary fallback={<GlobalErrorFallback />}>
      <ThemeProvider defaultTheme="system" storageKey="united-hrms-theme">
        <AuthProvider>
          <QueryProvider>
            <TooltipProvider delayDuration={200}>
              {children}
              <Toaster richColors closeButton position="top-right" />
            </TooltipProvider>
          </QueryProvider>
        </AuthProvider>
      </ThemeProvider>
    </ErrorBoundary>
  );
}
