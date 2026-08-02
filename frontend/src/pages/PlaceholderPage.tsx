import { Construction } from "lucide-react";

import { PageHeader } from "@/components/common/PageHeader";

interface PlaceholderPageProps {
  title: string;
  description?: string;
}

/**
 * Generic stand-in for every dashboard module route until that module's own
 * phase replaces it with a real page (see app/router/routes.tsx). Renders
 * inside DashboardLayout's `<Outlet />`, so it already gets the sidebar,
 * topbar, and content padding for free.
 */
export function PlaceholderPage({ title, description }: PlaceholderPageProps) {
  return (
    <div>
      <PageHeader title={title} description={description} />
      <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-border px-6 py-24 text-center">
        <div className="flex size-12 items-center justify-center rounded-full bg-muted">
          <Construction className="size-6 text-muted-foreground" aria-hidden="true" />
        </div>
        <div className="space-y-1">
          <h2 className="text-sm font-medium text-foreground">Coming soon</h2>
          <p className="max-w-sm text-sm text-muted-foreground">
            This module hasn&apos;t been built yet. Its page will replace this placeholder without
            any change to the surrounding layout or navigation.
          </p>
        </div>
      </div>
    </div>
  );
}
