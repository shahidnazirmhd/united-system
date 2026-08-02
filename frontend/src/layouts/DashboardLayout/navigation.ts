import {
  Bell,
  Boxes,
  CalendarClock,
  ClipboardCheck,
  Clock,
  LayoutDashboard,
  Settings,
  ShieldCheck,
  Users,
  type LucideIcon,
} from "lucide-react";

import { ROUTE_PATHS } from "@/app/router/routePaths";

export interface DashboardNavItem {
  label: string;
  path: string;
  icon: LucideIcon;
  /**
   * RBAC review round: any-of permission codes required for this item to
   * even be visible in the sidebar — undefined/empty means "no permission
   * needed" (every authenticated user sees it, e.g. Dashboard/Approvals/the
   * still-unbuilt placeholder modules). Filtered in Sidebar.tsx via
   * `useHasAnyPermission` (lib/auth/usePermission.ts) — this is what makes
   * "Users should only see modules they have permission for" actually true,
   * replacing the old "every nav item always visible, only the page decides
   * access" precedent (that precedent is exactly what the review flagged as
   * a bug: a Leave/Approvals-only user could still see and open User
   * Management). The backend's own `HasPermission` checks on every endpoint
   * remain the real enforcement boundary regardless — this only controls
   * what's shown.
   */
  anyOfPermissions?: string[];
}

/**
 * Data-driven sidebar navigation. Adding a future module's nav entry means
 * adding one object here — Sidebar.tsx itself never changes (Open/Closed
 * principle applied to navigation). Business Trips was removed entirely
 * (RBAC/UX review round) — no backend module ever existed for it, only this
 * placeholder tab, so removing the nav entry and its route below is the
 * whole change.
 */
export const DASHBOARD_NAV_ITEMS: DashboardNavItem[] = [
  { label: "Dashboard", path: ROUTE_PATHS.dashboard.home, icon: LayoutDashboard },
  {
    label: "Employees",
    path: ROUTE_PATHS.dashboard.employees,
    icon: Users,
    anyOfPermissions: ["employees.view_employees", "employees.manage_employees"],
  },
  {
    label: "Leave",
    path: ROUTE_PATHS.dashboard.leave,
    icon: CalendarClock,
    anyOfPermissions: ["leave.view_leave", "leave.manage_leave"],
  },
  { label: "Approvals", path: ROUTE_PATHS.dashboard.approvals, icon: ClipboardCheck },
  {
    label: "Attendance",
    path: ROUTE_PATHS.dashboard.attendance,
    icon: Clock,
    anyOfPermissions: ["attendance.view_attendance", "attendance.manage_holidays"],
  },
  { label: "Asset Requests", path: ROUTE_PATHS.dashboard.assetRequests, icon: Boxes },
  { label: "Notifications", path: ROUTE_PATHS.dashboard.notifications, icon: Bell },
  {
    label: "Users",
    path: ROUTE_PATHS.dashboard.users,
    icon: ShieldCheck,
    anyOfPermissions: ["identity.view_users", "identity.manage_users"],
  },
];

export const DASHBOARD_SECONDARY_NAV_ITEMS: DashboardNavItem[] = [
  {
    label: "Settings",
    path: ROUTE_PATHS.dashboard.settings,
    icon: Settings,
    anyOfPermissions: ["settings.view_settings", "settings.manage_settings"],
  },
];
