import { CalendarHeart } from "lucide-react";

import { DashboardWidgetCard } from "@/modules/dashboard/components/DashboardWidgetCard";
import { useUpcomingHolidaysQuery } from "@/modules/dashboard/hooks/useDashboardQueries";
import { useHasPermission } from "@/lib/auth/usePermission";
import { formatDate } from "@/utils";

/** Upcoming Holidays, gated on `attendance.view_attendance`. */
export function UpcomingHolidaysCard() {
  const canView = useHasPermission("attendance.view_attendance");
  const { data, isLoading, isError, refetch } = useUpcomingHolidaysQuery(5, canView);

  if (!canView) {
    return null;
  }

  return (
    <DashboardWidgetCard
      title="Upcoming Holidays"
      icon={CalendarHeart}
      isLoading={isLoading}
      isError={isError}
      onRetry={() => void refetch()}
      isEmpty={(data ?? []).length === 0}
      emptyTitle="No upcoming holidays"
      emptyDescription="Holidays added in Attendance will show up here once they're upcoming."
    >
      <ul className="divide-y divide-border">
        {(data ?? []).map((holiday) => (
          <li key={holiday.id} className="flex items-center justify-between gap-3 py-2.5 first:pt-0 last:pb-0">
            <span className="truncate text-sm font-medium text-foreground">{holiday.name}</span>
            <span className="shrink-0 text-xs text-muted-foreground">{formatDate(holiday.holidayDate)}</span>
          </li>
        ))}
      </ul>
    </DashboardWidgetCard>
  );
}
