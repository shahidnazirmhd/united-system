import type { ReactNode } from "react";

import { Outlet } from "react-router-dom";

import { Logo } from "@/components/common/Logo";

interface MinimalLayoutProps {
  children?: ReactNode;
}

/**
 * Bare-bones shell for standalone pages that don't need the full dashboard
 * chrome or the auth-card treatment — 404s, error pages, maintenance
 * notices, legal/standalone content. Just a brand mark and a content area.
 *
 * Accepts an optional `children` prop so it can be used two ways: as a
 * router layout route (`<MinimalLayout />`, renders its matched child route
 * via `<Outlet />`), or directly with explicit content (see
 * app/error/RouteErrorBoundary.tsx, which needs this layout's chrome but
 * isn't itself a route being rendered through the router).
 */
export function MinimalLayout({ children }: MinimalLayoutProps) {
  return (
    <div className="flex min-h-screen flex-col bg-background">
      <header className="border-b border-border">
        <div className="container flex h-16 items-center">
          <Logo />
        </div>
      </header>
      <main className="flex flex-1 flex-col">{children ?? <Outlet />}</main>
    </div>
  );
}
