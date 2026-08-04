import { Building2, UserCheck, UserPlus, Users, UserX } from "lucide-react";

import { DashboardWidgetCard } from "@/modules/dashboard/components/DashboardWidgetCard";
import { CategoryBarChart } from "@/modules/dashboard/components/CategoryBarChart";
import { DonutChart } from "@/modules/dashboard/components/DonutChart";
import { KpiCard } from "@/modules/dashboard/components/KpiCard";
import { useEmployeeStatisticsQuery } from "@/modules/dashboard/hooks/useDashboardQueries";
import { useHasPermission } from "@/lib/auth/usePermission";

const EMPLOYMENT_TYPE_LABELS: Record<string, string> = {
  full_time: "Full-time",
  part_time: "Part-time",
  contract: "Contract",
  intern: "Intern",
};

function labelEmploymentType(code: string): string {
  return EMPLOYMENT_TYPE_LABELS[code] ?? code;
}

// HR Leave Workflow round, item 3 — this module's own local copy of the
// display labels, deliberately not imported from `modules/employees`
// (feature modules stay independent of each other — see this codebase's
// existing "Dashboard never imports another feature module's components"
// discipline). Mirrors `modules/employees/types/employee.types
// .CURRENT_STATUS_LABELS` in wording only.
const CURRENT_STATUS_LABELS: Record<string, string> = {
  not_joined: "Not Joined",
  working: "Working",
  sick_leave: "Sick Leave",
  annual_leave: "Annual Leave",
  terminated: "Terminated",
  resigned: "Resigned",
};

function labelCurrentStatus(code: string): string {
  return CURRENT_STATUS_LABELS[code] ?? code.replace(/_/g, " ");
}

/**
 * Employee Statistics + Department Statistics, gated on
 * `employees.view_employees`. Composes the generic `KpiCard`/
 * `DashboardWidgetCard`/`CategoryBarChart`/`DonutChart` building blocks —
 * this file itself has no chart-rendering logic of its own, only layout and
 * data shaping, so a future KPI or breakdown is a few added lines here, not
 * a new chart component.
 */
export function EmployeeStatisticsSection() {
  const canView = useHasPermission("employees.view_employees");
  const { data, isLoading, isError, refetch } = useEmployeeStatisticsQuery(canView);

  if (!canView) {
    return null;
  }

  const departmentData =
    data?.departmentBreakdown.map((stat) => ({ name: stat.departmentName, value: stat.count })) ??
    [];
  const employmentTypeData =
    data && Object.keys(data.employmentTypeBreakdown).length > 0
      ? Object.entries(data.employmentTypeBreakdown).map(([code, count]) => ({
          name: labelEmploymentType(code),
          value: count,
        }))
      : [];
  // HR Leave Workflow round, item 3 — status distribution across every
  // Current Status value (Working, Annual Leave, Sick Leave, Not Joined,
  // Resigned, Terminated), sourced from the same `EmployeeStatisticsResponse
  // .current_status_breakdown` field the backend already returns (Phase 14)
  // — no backend change needed for this widget, only this new section of
  // the existing statistics card. Updates automatically in real time via
  // `useEmployeeStatisticsQuery`'s existing polling `refetchInterval`,
  // matching every other dashboard widget's "auto-refresh" behavior.
  const currentStatusData =
    data && Object.keys(data.currentStatusBreakdown).length > 0
      ? Object.entries(data.currentStatusBreakdown).map(([code, count]) => ({
          name: labelCurrentStatus(code),
          value: count,
        }))
      : [];

  return (
    <section className="space-y-4">
      <h2 className="text-lg font-semibold tracking-tight text-foreground">Employee Statistics</h2>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard
          label="Total Employees"
          value={data?.totalEmployees ?? 0}
          icon={Users}
          isLoading={isLoading}
        />
        <KpiCard
          label="Active"
          value={data?.activeCount ?? 0}
          icon={UserCheck}
          isLoading={isLoading}
        />
        <KpiCard
          label="Inactive"
          value={data?.inactiveCount ?? 0}
          icon={UserX}
          isLoading={isLoading}
        />
        <KpiCard
          label="New Hires This Month"
          value={data?.newHiresThisMonth ?? 0}
          icon={UserPlus}
          isLoading={isLoading}
        />
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <DashboardWidgetCard
          title="Department Statistics"
          icon={Building2}
          isLoading={isLoading}
          isError={isError}
          onRetry={() => void refetch()}
          isEmpty={departmentData.length === 0}
          emptyTitle="No departments yet"
          emptyDescription="Headcount by department will appear here once employees are assigned to departments."
        >
          <CategoryBarChart data={departmentData} />
        </DashboardWidgetCard>
        <DashboardWidgetCard
          title="Employment Type Breakdown"
          isLoading={isLoading}
          isError={isError}
          onRetry={() => void refetch()}
          isEmpty={employmentTypeData.length === 0}
        >
          <DonutChart data={employmentTypeData} />
        </DashboardWidgetCard>
        <DashboardWidgetCard
          title="Employee Current Status"
          icon={UserCheck}
          isLoading={isLoading}
          isError={isError}
          onRetry={() => void refetch()}
          isEmpty={currentStatusData.length === 0}
          emptyTitle="No status data yet"
          emptyDescription="Working/On Leave/Not Joined and other Current Status counts will appear here."
        >
          <DonutChart data={currentStatusData} />
        </DashboardWidgetCard>
      </div>
    </section>
  );
}
