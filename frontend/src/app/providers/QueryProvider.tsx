import type { ReactNode } from "react";

import { QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";

import { queryClient } from "@/lib/api/queryClient";

interface QueryProviderProps {
  children: ReactNode;
}

/**
 * Single TanStack Query provider for the whole app — every future module's
 * data fetching goes through this one QueryClient (src/lib/api/queryClient.ts),
 * never a module-local instance. Devtools only mount in development builds;
 * `import.meta.env.DEV` is stripped out of production bundles by Vite, so
 * this has zero production cost.
 */
export function QueryProvider({ children }: QueryProviderProps) {
  return (
    <QueryClientProvider client={queryClient}>
      {children}
      {import.meta.env.DEV ? (
        <ReactQueryDevtools initialIsOpen={false} buttonPosition="bottom-right" />
      ) : null}
    </QueryClientProvider>
  );
}
