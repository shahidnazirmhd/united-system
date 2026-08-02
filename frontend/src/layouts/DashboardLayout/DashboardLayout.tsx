import { useState } from "react";

import { Outlet } from "react-router-dom";

import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { Sidebar } from "@/layouts/DashboardLayout/components/Sidebar";
import { Topbar } from "@/layouts/DashboardLayout/components/Topbar";

/**
 * Primary authenticated-app shell: a fixed sidebar on large screens, a
 * slide-over Sheet sidebar on small screens, a topbar, and a scrollable
 * content area rendering the matched route via `<Outlet />`. Every
 * dashboard-module route (see app/router/routes.tsx) nests under this
 * layout, so adding a new module never touches this file.
 *
 * Round 15 item 1 fix: this outer container used to be `min-h-screen`,
 * which only sets a *minimum* height — the browser is free to leave its
 * resolved height as `auto`, which makes `Sidebar.tsx`'s `h-full` an
 * ambiguous percentage (no definite parent height to resolve against),
 * so the sidebar could end up shorter than the viewport with blank space
 * below "Settings" instead of it being pinned to the true bottom edge.
 * `h-screen` (a definite 100vh) plus `overflow-hidden` here — with `<main>`
 * still doing its own internal `overflow-y-auto` — guarantees the aside's
 * `h-full` always resolves to exactly the viewport height.
 */
export function DashboardLayout() {
  const [isMobileNavOpen, setIsMobileNavOpen] = useState(false);

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <Sidebar className="hidden lg:flex" />

      <Sheet open={isMobileNavOpen} onOpenChange={setIsMobileNavOpen}>
        <SheetContent side="left" className="w-64 p-0">
          {/* Visually hidden — Radix Dialog requires an accessible title even
              when the sheet's own Sidebar content already communicates its
              purpose visually. */}
          <SheetTitle className="sr-only">Navigation menu</SheetTitle>
          <Sidebar onNavigate={() => setIsMobileNavOpen(false)} />
        </SheetContent>
      </Sheet>

      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar onOpenMobileNav={() => setIsMobileNavOpen(true)} />
        <main className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
