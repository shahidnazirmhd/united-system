import { CalendarDays, CalendarPlus, ClipboardCheck, UserPlus, type LucideIcon } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { ROUTE_PATHS } from "@/app/router/routePaths";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useHasAnyPermission } from "@/lib/auth/usePermission";

interface QuickAction {
  label: string;
  icon: LucideIcon;
  path: string;
  anyOfPermissions?: string[];
}

const QUICK_ACTIONS: QuickAction[] = [
  {
    label: "Add Employee",
    icon: UserPlus,
    path: ROUTE_PATHS.dashboard.employeesNew,
    anyOfPermissions: ["employees.manage_employees"],
  },
  {
    label: "Leave Requests",
    icon: CalendarDays,
    path: ROUTE_PATHS.dashboard.leave,
    anyOfPermissions: ["leave.view_leave", "leave.manage_leave"],
  },
  { label: "Review Approvals", icon: ClipboardCheck, path: ROUTE_PATHS.dashboard.approvals },
  {
    label: "Manage Holidays",
    icon: CalendarPlus,
    path: ROUTE_PATHS.dashboard.attendanceHolidays,
    anyOfPermissions: ["attendance.manage_holidays"],
  },
];

function QuickActionButton({ action }: { action: QuickAction }) {
  const navigate = useNavigate();
  // A dedicated sub-component (rather than calling the hook inline inside
  // `QUICK_ACTIONS.map(...)`) so each action's visibility check is its own,
  // unconditional hook call — the same reasoning any list of components
  // that each need their own hook state already follows in this codebase.
  const isVisible = useHasAnyPermission(action.anyOfPermissions ?? []);

  if (!isVisible) {
    return null;
  }

  return (
    <Button
      variant="outline"
      className="h-auto flex-col items-center gap-2 py-4"
      onClick={() => navigate(action.path)}
    >
      <action.icon className="size-5" aria-hidden="true" />
      <span className="text-xs font-medium">{action.label}</span>
    </Button>
  );
}

/**
 * Static shortcut grid into each module's existing create/manage screen —
 * no new routes, just permission-gated links to what already exists.
 * `QUICK_ACTIONS` is the extensibility point: a future module adds one
 * object here, nothing else in this file changes.
 */
export function QuickActionsCard() {
  // Purely a convenience early-exit: if none of these actions would be
  // visible anyway, skip rendering the whole card instead of an empty shell.
  const hasAnyAction = useHasAnyPermission(
    Array.from(new Set(QUICK_ACTIONS.flatMap((action) => action.anyOfPermissions ?? []))),
  );
  const alwaysVisibleActionExists = QUICK_ACTIONS.some((action) => !action.anyOfPermissions);

  if (!hasAnyAction && !alwaysVisibleActionExists) {
    return null;
  }

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">Quick Actions</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {QUICK_ACTIONS.map((action) => (
            <QuickActionButton key={action.label} action={action} />
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
