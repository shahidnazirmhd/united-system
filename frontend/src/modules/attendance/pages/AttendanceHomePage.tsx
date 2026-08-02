import { CalendarDays } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { ROUTE_PATHS } from "@/app/router/routePaths";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/common";
import { useHasPermission } from "@/lib/auth/usePermission";

/**
 * Attendance module landing page. Only Holiday Management is implemented so
 * far (item 5 of the round-14 request) — actual clock-in/out attendance
 * tracking is future work, so this page is a thin hub with a header action
 * into Holiday Management, mirroring how Departments is reached from the
 * Employee List page rather than getting its own sidebar entry.
 */
export function AttendanceHomePage() {
  const navigate = useNavigate();
  const canViewHolidays = useHasPermission("attendance.view_attendance");

  return (
    <div>
      <PageHeader
        title="Attendance"
        description="Attendance tracking and corrections will live here. Holiday Management is available now."
        actions={
          canViewHolidays ? (
            <Button onClick={() => navigate(ROUTE_PATHS.dashboard.attendanceHolidays)}>
              <CalendarDays className="size-4" aria-hidden="true" />
              Manage Holidays
            </Button>
          ) : undefined
        }
      />
      <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-border px-6 py-24 text-center">
        <div className="flex size-12 items-center justify-center rounded-full bg-muted">
          <CalendarDays className="size-6 text-muted-foreground" aria-hidden="true" />
        </div>
        <div className="space-y-1">
          <h2 className="text-sm font-medium text-foreground">Attendance tracking coming soon</h2>
          <p className="max-w-sm text-sm text-muted-foreground">
            Use Manage Holidays above to define upcoming holidays used by the Leave module&apos;s
            working-day calculations.
          </p>
        </div>
      </div>
    </div>
  );
}
