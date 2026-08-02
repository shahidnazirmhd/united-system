import { NavLink } from "react-router-dom";

import { Logo } from "@/components/common/Logo";
import { Separator } from "@/components/ui/separator";
import {
  DASHBOARD_NAV_ITEMS,
  DASHBOARD_SECONDARY_NAV_ITEMS,
  type DashboardNavItem,
} from "@/layouts/DashboardLayout/navigation";
import { useCurrentUserQuery } from "@/lib/auth";
import { cn } from "@/lib/utils";

interface SidebarProps {
  className?: string;
  onNavigate?: () => void;
}

function navLinkClassName({ isActive }: { isActive: boolean }): string {
  return cn(
    "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
    isActive
      ? "bg-sidebar-accent text-sidebar-accent-foreground"
      : "text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
  );
}

/** Pure (non-hook) check against an already-fetched permission set — kept
 * separate from `useHasAnyPermission` (lib/auth/usePermission.ts) because
 * this filters a whole array of nav items in one pass; calling a hook once
 * per item inside `.filter()` would violate the Rules of Hooks (a variable
 * number of hook calls across renders). One `useCurrentUserQuery()` call up
 * front, then this plain function per item, keeps the same permission logic
 * without that problem. */
function isNavItemVisible(item: DashboardNavItem, heldPermissionCodes: string[] | undefined): boolean {
  if (!item.anyOfPermissions || item.anyOfPermissions.length === 0) {
    return true;
  }
  if (!heldPermissionCodes) {
    return false;
  }
  return item.anyOfPermissions.some((code) => heldPermissionCodes.includes(code));
}

/**
 * Primary navigation. Rendered twice by DashboardLayout: once as a
 * permanently-visible desktop column (`className="hidden lg:flex"`), once
 * inside a Sheet for mobile (no className override, so it fills the sheet).
 * Both usages share this single component — no duplicated markup.
 *
 * RBAC review round: nav items are now filtered by the caller's own
 * `permissionCodes` (see `navigation.ts`'s `anyOfPermissions` field) —
 * a Leave/Approvals-only user no longer even sees "Users" in this list.
 */
export function Sidebar({ className, onNavigate }: SidebarProps) {
  const { data: currentUser } = useCurrentUserQuery();
  const visiblePrimaryItems = DASHBOARD_NAV_ITEMS.filter((item) =>
    isNavItemVisible(item, currentUser?.permissionCodes),
  );
  const visibleSecondaryItems = DASHBOARD_SECONDARY_NAV_ITEMS.filter((item) =>
    isNavItemVisible(item, currentUser?.permissionCodes),
  );

  return (
    <aside
      className={cn(
        "flex h-full w-64 shrink-0 flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground",
        className,
      )}
    >
      <div className="flex h-16 shrink-0 items-center px-6">
        <Logo />
      </div>
      <Separator className="bg-sidebar-border" />
      <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4" aria-label="Primary">
        {visiblePrimaryItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            end={item.path === "/"}
            onClick={onNavigate}
            className={navLinkClassName}
          >
            <item.icon className="size-4 shrink-0" aria-hidden="true" />
            {item.label}
          </NavLink>
        ))}
      </nav>
      <Separator className="bg-sidebar-border" />
      <div className="shrink-0 space-y-1 px-3 py-4">
        {visibleSecondaryItems.map((item) => (
          <NavLink key={item.path} to={item.path} onClick={onNavigate} className={navLinkClassName}>
            <item.icon className="size-4 shrink-0" aria-hidden="true" />
            {item.label}
          </NavLink>
        ))}
      </div>
    </aside>
  );
}
