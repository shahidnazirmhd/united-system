import { PageHeader } from "@/components/common/PageHeader";
import {
  EmployeeStatisticsSection,
  LeaveStatisticsSection,
  PendingApprovalsCard,
  QuickActionsCard,
  RecentActivityCard,
  UpcomingHolidaysCard,
} from "@/modules/dashboard";

/**
 * The dashboard's index route (`/`) — a live, auto-refreshing overview
 * composed entirely from `modules/dashboard`'s own widgets. Every widget
 * below independently fetches its own data (via TanStack Query's
 * `refetchInterval`, see `useDashboardQueries.ts`) and independently decides
 * its own visibility (via `useHasPermission`/`useHasAnyPermission`), so this
 * page itself has no data-fetching or permission logic of its own — it is
 * purely layout. Adding a future widget (a new KPI, chart, or list) means
 * adding one more line to this grid, never editing an existing widget.
 *
 * Attendance Summary is intentionally not included: this codebase's
 * `apps.attendance` module covers Holiday Management only — there is no
 * clock-in/out or daily attendance tracking data model yet (see
 * `apps.dashboard`'s module docstring) — so a real "Attendance Summary"
 * widget would have nothing genuine to show. Upcoming Holidays (below)
 * is the one Attendance-sourced widget with real data behind it.
 */
export function DashboardHomePage() {
  return (
    <div className="space-y-8">
      <PageHeader
        title="Dashboard"
        description="A live overview of your organization — updates automatically, no refresh needed."
      />

      <QuickActionsCard />

      <EmployeeStatisticsSection />

      <LeaveStatisticsSection />

      <div className="grid gap-4 lg:grid-cols-3">
        <PendingApprovalsCard />
        <RecentActivityCard />
        <UpcomingHolidaysCard />
      </div>
    </div>
  );
}
