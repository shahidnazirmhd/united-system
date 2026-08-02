import { Activity } from "lucide-react";

import { Badge, type BadgeProps } from "@/components/ui/badge";
import { DashboardWidgetCard } from "@/modules/dashboard/components/DashboardWidgetCard";
import { useRecentActivityQuery } from "@/modules/dashboard/hooks/useDashboardQueries";
import { useHasPermission } from "@/lib/auth/usePermission";
import { formatRelativeToNow } from "@/utils";

// Deliberately Dashboard's own status->badge mapping, not a re-import of
// `modules/leave`'s `LeaveStatusBadge` — `RecentActivityItem.status` is
// this module's own DTO field (a plain string), not Leave's
// `LeaveRequestStatus` type, matching the backend's own "Dashboard defines
// its own copies, never reaches into another module's contract directly"
// choice (see `apps.dashboard.application.dtos`'s docstring). The status
// values themselves happen to overlap with Leave's today, but that is an
// implementation detail Dashboard doesn't depend on.
const VARIANT_BY_STATUS: Record<string, NonNullable<BadgeProps["variant"]>> = {
  draft: "secondary",
  pending: "warning",
  approved: "success",
  rejected: "destructive",
  cancelled: "secondary",
};

const LABEL_BY_STATUS: Record<string, string> = {
  draft: "Draft",
  pending: "Pending",
  approved: "Approved",
  rejected: "Rejected",
  cancelled: "Cancelled",
};

function StatusBadge({ status }: { status: string }) {
  return <Badge variant={VARIANT_BY_STATUS[status] ?? "outline"}>{LABEL_BY_STATUS[status] ?? status}</Badge>;
}

/**
 * "Recent Activity" (and, until this app has a real Notifications backend
 * of its own, the closest honest stand-in for "Recent Notifications" too —
 * see this module's `dashboard.types.ts` docstring) — every leave request
 * whose status changed most recently, across every employee. Gated on
 * `leave.view_leave`, the same permission that already governs Leave's own
 * HR-wide processing queue this reuses (see the backend's
 * `LeaveServiceStatisticsAdapter.get_recent_activity` docstring).
 */
export function RecentActivityCard() {
  const canView = useHasPermission("leave.view_leave");
  const { data, isLoading, isError, refetch } = useRecentActivityQuery(10, canView);

  if (!canView) {
    return null;
  }

  return (
    <DashboardWidgetCard
      title="Recent Activity"
      icon={Activity}
      isLoading={isLoading}
      isError={isError}
      onRetry={() => void refetch()}
      isEmpty={(data ?? []).length === 0}
      emptyTitle="No recent activity"
      emptyDescription="Leave requests that are applied for, approved, rejected, or cancelled will show up here."
    >
      <ul className="divide-y divide-border">
        {(data ?? []).map((item) => (
          <li key={item.leaveRequestId} className="flex items-center justify-between gap-3 py-2.5 first:pt-0 last:pb-0">
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-foreground">
                {item.employeeName ?? "Unknown employee"}
                {item.employeeCode ? (
                  <span className="ml-1.5 text-xs font-normal text-muted-foreground">{item.employeeCode}</span>
                ) : null}
              </p>
              <p className="truncate text-xs text-muted-foreground">
                {item.leaveTypeName ?? "Leave"} · {formatRelativeToNow(item.updatedAt ?? item.startDate)}
              </p>
            </div>
            <StatusBadge status={item.status} />
          </li>
        ))}
      </ul>
    </DashboardWidgetCard>
  );
}
