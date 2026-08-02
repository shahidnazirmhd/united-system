import { AlertTriangle } from "lucide-react";

import { Button } from "@/components/ui/button";

/**
 * Rendered by ErrorBoundary when a render-time crash escapes every other
 * safety net. Deliberately self-contained (no router, no layout, no data
 * fetching) — at this point we can't assume ANYTHING else in the tree still
 * works, including the router itself.
 */
export function GlobalErrorFallback() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 bg-background px-4 text-center">
      <div className="flex size-16 items-center justify-center rounded-full bg-destructive/10">
        <AlertTriangle className="size-8 text-destructive" aria-hidden="true" />
      </div>
      <div className="space-y-2">
        <h1 className="text-xl font-semibold text-foreground">Something went wrong</h1>
        <p className="max-w-md text-sm text-muted-foreground">
          An unexpected error occurred and this part of the application couldn&apos;t recover.
          Reloading the page usually fixes it.
        </p>
      </div>
      <Button onClick={() => window.location.assign("/")}>Reload application</Button>
    </div>
  );
}
