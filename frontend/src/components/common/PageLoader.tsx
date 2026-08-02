import { Loader2 } from "lucide-react";

interface PageLoaderProps {
  label?: string;
}

/**
 * Full-height loading state used as the Suspense fallback for lazy-loaded
 * route pages (see app/router/withSuspense.tsx). Also reusable inside any
 * page-level section that needs a centered "loading" state.
 */
export function PageLoader({ label = "Loading…" }: PageLoaderProps) {
  return (
    <div
      className="flex min-h-[50vh] w-full flex-col items-center justify-center gap-3 text-muted-foreground"
      role="status"
      aria-live="polite"
    >
      <Loader2 className="size-6 animate-spin" aria-hidden="true" />
      <span className="text-sm">{label}</span>
    </div>
  );
}
