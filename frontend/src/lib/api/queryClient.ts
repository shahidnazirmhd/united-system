import { QueryClient } from "@tanstack/react-query";

import { ApiError } from "@/lib/api/types";

/**
 * The one TanStack Query client for the whole application (provided in
 * app/providers/QueryProvider.tsx). Defaults are chosen deliberately:
 *  - `staleTime` > 0 so navigating between pages that share data doesn't
 *    trigger a redundant refetch on every mount.
 *  - `refetchOnWindowFocus: false` — a reasonable default for an internal
 *    HR tool where data doesn't change every second; individual queries can
 *    opt back in if a specific future screen genuinely needs it.
 *  - `retry` skips retrying 4xx `ApiError`s (a validation/permission/not-found
 *    error will fail identically on retry — only retry on network errors or
 *    5xx, where a transient failure is plausible).
 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60 * 1000,
      gcTime: 5 * 60 * 1000,
      refetchOnWindowFocus: false,
      retry: (failureCount, error) => {
        if (error instanceof ApiError && error.status !== null && error.status < 500) {
          return false;
        }
        return failureCount < 2;
      },
    },
    mutations: {
      retry: false,
    },
  },
});
