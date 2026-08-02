import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import type { ApiError, PagedResult } from "@/lib/api/types";
import { getEmployeeById, listEmployees } from "@/modules/employees/api/employeeApi";
import type { Employee, EmployeeListFilters } from "@/modules/employees/types/employee.types";

/**
 * Query key convention for this module: `["employees", "list", filters]` /
 * `["employees", "detail", id]` — mirrored by the mutation hooks
 * (useEmployeeMutations.ts) so a create/update/activate/deactivate can
 * invalidate exactly `["employees"]` and catch both shapes.
 */
export function useEmployeesQuery(
  filters: EmployeeListFilters,
): UseQueryResult<PagedResult<Employee>, ApiError> {
  return useQuery({
    queryKey: ["employees", "list", filters],
    queryFn: () => listEmployees(filters),
    placeholderData: (previousData) => previousData,
  });
}

export function useEmployeeQuery(employeeId: string | undefined): UseQueryResult<Employee, ApiError> {
  return useQuery({
    queryKey: ["employees", "detail", employeeId],
    queryFn: () => getEmployeeById(employeeId as string),
    enabled: Boolean(employeeId),
  });
}

/**
 * Feeds the head-employee <Select> on the Department form — same
 * `page_size: 100` "good enough for this phase's scope" reasoning as
 * `useDepartmentQueries.ts`'s `useAllDepartmentsQuery`. The Employee form's
 * own Manager field moved off this (unbounded-feeling, capped-at-100)
 * pattern to a real search-as-you-type combobox — see
 * `useEmployeeSearchQuery` below — since a flat dropdown of every employee
 * doesn't scale to a real organization's headcount. Department's picker
 * wasn't part of that request; it's a reasonable follow-up if asked.
 */
export function useAllEmployeesQuery(): UseQueryResult<PagedResult<Employee>, ApiError> {
  return useQuery({
    queryKey: ["employees", "list", { pageSize: 100, ordering: "first_name,last_name" }],
    queryFn: () => listEmployees({ pageSize: 100, ordering: "first_name,last_name" }),
    staleTime: 60_000,
  });
}

/**
 * Search-as-you-type source for `ManagerPickerField` — queries the same
 * `GET /employees/` endpoint the Employee List page already searches
 * (first name, last name, employee code, work email — see
 * EMPLOYEE_API.md), capped to a small page since this only ever feeds a
 * dropdown of matches, not a full listing.
 */
export function useEmployeeSearchQuery(search: string): UseQueryResult<PagedResult<Employee>, ApiError> {
  return useQuery({
    queryKey: ["employees", "list", "search", search, { pageSize: 10 }],
    queryFn: () => listEmployees({ search, pageSize: 10, ordering: "first_name,last_name" }),
    staleTime: 30_000,
  });
}
