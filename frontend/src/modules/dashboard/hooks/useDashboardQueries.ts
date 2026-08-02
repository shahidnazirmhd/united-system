import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import { createQueryKeyFactory } from "@/lib/api";
import type { ApiError } from "@/lib/api/types";
import {
  getEmployeeStatistics,
  getLeaveStatistics,
  getRecentActivity,
  getUpcomingHolidays,
} from "@/modules/dashboard/api/dashboardApi";
import type {
  EmployeeStatistics,
  LeaveStatistics,
  RecentActivityItem,
  UpcomingHoliday,
} from "@/modules/dashboard/types/dashboard.types";

export const dashboardKeys = createQueryKeyFactory<void>("dashboard");

export const DEFAULT_RECENT_ACTIVITY_LIMIT = 10;
export const DEFAULT_UPCOMING_HOLIDAYS_LIMIT = 5;

// Distinct poll intervals per widget (not one shared interval) — the whole
// point of four granular backend endpoints instead of one "get everything"
// payload (see the backend's DashboardService docstring): headcount/
// department shape barely changes minute to minute, while "recent activity"
// is the one widget most likely to go stale while someone is looking at it.
// This is what makes "dashboard updates automatically, no page refresh"
// true without over-polling data that never changes that often.
const EMPLOYEE_STATISTICS_REFETCH_INTERVAL_MS = 60_000;
const LEAVE_STATISTICS_REFETCH_INTERVAL_MS = 30_000;
const RECENT_ACTIVITY_REFETCH_INTERVAL_MS = 15_000;
const UPCOMING_HOLIDAYS_REFETCH_INTERVAL_MS = 5 * 60_000;

/** `enabled` on every hook below defaults to `true` but accepts `false` so a
 * widget that has already decided (via `useHasPermission`) that its caller
 * can't see this data never fires the request at all — see each widget
 * component for how it's used. */
export function useEmployeeStatisticsQuery(enabled = true): UseQueryResult<EmployeeStatistics, ApiError> {
  return useQuery({
    queryKey: [...dashboardKeys.all, "employee-statistics"] as const,
    queryFn: getEmployeeStatistics,
    refetchInterval: EMPLOYEE_STATISTICS_REFETCH_INTERVAL_MS,
    enabled,
  });
}

export function useLeaveStatisticsQuery(enabled = true): UseQueryResult<LeaveStatistics, ApiError> {
  return useQuery({
    queryKey: [...dashboardKeys.all, "leave-statistics"] as const,
    queryFn: getLeaveStatistics,
    refetchInterval: LEAVE_STATISTICS_REFETCH_INTERVAL_MS,
    enabled,
  });
}

export function useRecentActivityQuery(
  limit: number = DEFAULT_RECENT_ACTIVITY_LIMIT,
  enabled = true,
): UseQueryResult<RecentActivityItem[], ApiError> {
  return useQuery({
    queryKey: [...dashboardKeys.all, "recent-activity", limit] as const,
    queryFn: () => getRecentActivity(limit),
    refetchInterval: RECENT_ACTIVITY_REFETCH_INTERVAL_MS,
    enabled,
  });
}

export function useUpcomingHolidaysQuery(
  limit: number = DEFAULT_UPCOMING_HOLIDAYS_LIMIT,
  enabled = true,
): UseQueryResult<UpcomingHoliday[], ApiError> {
  return useQuery({
    queryKey: [...dashboardKeys.all, "upcoming-holidays", limit] as const,
    queryFn: () => getUpcomingHolidays(limit),
    refetchInterval: UPCOMING_HOLIDAYS_REFETCH_INTERVAL_MS,
    enabled,
  });
}
