import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import type { ApiError, PagedResult } from "@/lib/api/types";
import { listHolidays } from "@/modules/attendance/api/holidayApi";
import type { Holiday, HolidayListFilters } from "@/modules/attendance/types/holiday.types";

export function useHolidaysQuery(
  filters: HolidayListFilters = {},
): UseQueryResult<PagedResult<Holiday>, ApiError> {
  return useQuery({
    queryKey: ["holidays", "list", filters],
    queryFn: () => listHolidays(filters),
    placeholderData: (previousData) => previousData,
  });
}
