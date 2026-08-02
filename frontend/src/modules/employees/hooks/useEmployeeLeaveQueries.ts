import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import type { ApiError, PagedResult } from "@/lib/api/types";
import { getEmployeeLeaveBalance, listEmployeeLeaveHistory } from "@/modules/employees/api/employeeLeaveApi";
import type {
  EmployeeLeaveBalance,
  EmployeeLeaveHistoryFilters,
  EmployeeLeaveRequest,
} from "@/modules/employees/types/employeeLeave.types";

/** Backs Employee Details' own Leave section (Phase 13 review requirement)
 * — query keys namespaced under `["employees", "leave", ...]`, distinct
 * from `modules/leave`'s own `["leave", ...]` keys (different module,
 * different cache entries, even though both ultimately read the same
 * backend rows). */
export function useEmployeeLeaveBalanceQuery(
  employeeId: string | undefined,
  year?: number,
): UseQueryResult<EmployeeLeaveBalance[], ApiError> {
  return useQuery({
    queryKey: ["employees", "leave", "balance", employeeId ?? "", year ?? "current"],
    queryFn: () => getEmployeeLeaveBalance(employeeId as string, year),
    enabled: Boolean(employeeId),
  });
}

export function useEmployeeLeaveHistoryQuery(
  employeeId: string | undefined,
  filters: EmployeeLeaveHistoryFilters,
): UseQueryResult<PagedResult<EmployeeLeaveRequest>, ApiError> {
  return useQuery({
    queryKey: ["employees", "leave", "history", employeeId ?? "", filters],
    queryFn: () => listEmployeeLeaveHistory(employeeId as string, filters),
    enabled: Boolean(employeeId),
    placeholderData: (previousData) => previousData,
  });
}
