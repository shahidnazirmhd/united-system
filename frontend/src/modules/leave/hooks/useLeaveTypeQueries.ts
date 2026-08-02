import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import type { ApiError, PagedResult } from "@/lib/api/types";
import { listLeaveTypesForManagement } from "@/modules/leave/api/leaveApi";
import { leaveKeys } from "@/modules/leave/hooks/useLeaveQueries";
import type { LeaveType, LeaveTypeListFilters } from "@/modules/leave/types/leave.types";

export function useManagedLeaveTypesQuery(
  filters: LeaveTypeListFilters,
): UseQueryResult<PagedResult<LeaveType>, ApiError> {
  return useQuery({
    queryKey: [...leaveKeys.all, "types", "manage", filters] as const,
    queryFn: () => listLeaveTypesForManagement(filters),
    placeholderData: (previousData) => previousData,
  });
}
