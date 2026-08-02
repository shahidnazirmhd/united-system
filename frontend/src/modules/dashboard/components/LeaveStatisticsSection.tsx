import { CalendarClock, CalendarDays, CheckCircle2, Clock } from "lucide-react";

import { DashboardWidgetCard } from "@/modules/dashboard/components/DashboardWidgetCard";
import { DonutChart } from "@/modules/dashboard/components/DonutChart";
import { KpiCard } from "@/modules/dashboard/components/KpiCard";
import { LeaveTrendChart } from "@/modules/dashboard/components/LeaveTrendChart";
import { useLeaveStatisticsQuery } from "@/modules/dashboard/hooks/useDashboardQueries";
import { useHasPermission } from "@/lib/auth/usePermission";

/**
 * Leave Statistics, gated on `leave.view_leave` — same composition pattern
 * as `EmployeeStatisticsSection` (see its docstring).
 */
export function LeaveStatisticsSection() {
  const canView = useHasPermission("leave.view_leave");
  const { data, isLoading, isError, refetch } = useLeaveStatisticsQuery(canView);

  if (!canView) {
    return null;
  }

  const pendingCount = data?.statusBreakdown.pending ?? 0;
  const approvedCount = data?.statusBreakdown.approved ?? 0;
  const leaveTypeData =
    data?.leaveTypeBreakdown.map((stat) => ({ name: stat.leaveTypeName, value: stat.count })) ?? [];

  return (
    <section className="space-y-4">
      <h2 className="text-lg font-semibold tracking-tight text-foreground">Leave Statistics</h2>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard label="On Leave Today" value={data?.onLeaveTodayCount ?? 0} icon={CalendarDays} isLoading={isLoading} />
        <KpiCard label="Pending Requests" value={pendingCount} icon={Clock} isLoading={isLoading} />
        <KpiCard label="Approved Requests" value={approvedCount} icon={CheckCircle2} isLoading={isLoading} />
        <KpiCard
          label="Total Requests"
          value={Object.values(data?.statusBreakdown ?? {}).reduce((sum, count) => sum + count, 0)}
          icon={CalendarClock}
          isLoading={isLoading}
        />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <DashboardWidgetCard
          title="Leave Applications Trend"
          isLoading={isLoading}
          isError={isError}
          onRetry={() => void refetch()}
          isEmpty={(data?.monthlyTrend ?? []).every((point) => point.count === 0)}
          emptyTitle="No leave applications yet"
          emptyDescription="Once employees start applying for leave, the monthly trend will appear here."
        >
          <LeaveTrendChart data={data?.monthlyTrend ?? []} />
        </DashboardWidgetCard>
        <DashboardWidgetCard
          title="Leave Type Breakdown"
          isLoading={isLoading}
          isError={isError}
          onRetry={() => void refetch()}
          isEmpty={leaveTypeData.length === 0}
        >
          <DonutChart data={leaveTypeData} />
        </DashboardWidgetCard>
      </div>
    </section>
  );
}
