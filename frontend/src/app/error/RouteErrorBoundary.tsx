import { AlertTriangle } from "lucide-react";
import { isRouteErrorResponse, useRouteError } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { MinimalLayout } from "@/layouts/MinimalLayout";

/**
 * React Router's `errorElement` for every top-level route (see
 * app/router/routes.tsx). Distinguishes a routing-level error (bad path,
 * thrown Response — none of which exist yet since no route has a loader in
 * this foundational phase, but the handling is ready for when one does)
 * from an unexpected thrown error, and renders inside MinimalLayout so the
 * user still sees consistent app chrome rather than a bare error page.
 */
export function RouteErrorBoundary() {
  const error = useRouteError();

  const status = isRouteErrorResponse(error) ? error.status : null;
  const title = status === 404 ? "Page not found" : "Something went wrong";
  const description = isRouteErrorResponse(error)
    ? (error.statusText ?? error.data)
    : "An unexpected error occurred while loading this page.";

  return (
    <MinimalLayout>
      <div className="flex flex-1 flex-col items-center justify-center gap-6 px-4 py-24 text-center">
        <div className="flex size-16 items-center justify-center rounded-full bg-destructive/10">
          <AlertTriangle className="size-8 text-destructive" aria-hidden="true" />
        </div>
        <div className="space-y-2">
          <h1 className="text-xl font-semibold text-foreground">{title}</h1>
          <p className="max-w-md text-sm text-muted-foreground">{String(description)}</p>
        </div>
        <div className="flex gap-3">
          <Button variant="outline" onClick={() => window.history.back()}>
            Go back
          </Button>
          <Button onClick={() => window.location.assign("/")}>Go to dashboard</Button>
        </div>
      </div>
    </MinimalLayout>
  );
}
