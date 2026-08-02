import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import type { ApiError, PagedResult } from "@/lib/api/types";
import { getDepartmentById, listDepartments } from "@/modules/employees/api/departmentApi";
import type { Department, DepartmentListFilters } from "@/modules/employees/types/department.types";

export function useDepartmentsQuery(
  filters: DepartmentListFilters = {},
): UseQueryResult<PagedResult<Department>, ApiError> {
  return useQuery({
    queryKey: ["departments", "list", filters],
    queryFn: () => listDepartments(filters),
    placeholderData: (previousData) => previousData,
  });
}

export function useDepartmentQuery(
  departmentId: string | undefined,
): UseQueryResult<Department, ApiError> {
  return useQuery({
    queryKey: ["departments", "detail", departmentId],
    queryFn: () => getDepartmentById(departmentId as string),
    enabled: Boolean(departmentId),
  });
}

/**
 * A large, unpaginated-feeling fetch (`page_size: 100`) used to feed the
 * department <Select> on the Employee form and the parent-department
 * <Select> on the Department form — see EMPLOYEE_API.md's note that
 * `page_size` caps at 100. Acceptable for this phase's scope (a handful of
 * departments per organization); an org with more than 100 departments
 * would need a searchable combobox instead, which is a real UI upgrade, not
 * a one-line change — deliberately deferred rather than built speculatively.
 */
export function useAllDepartmentsQuery(): UseQueryResult<PagedResult<Department>, ApiError> {
  return useQuery({
    queryKey: ["departments", "list", { pageSize: 100, ordering: "name" }],
    queryFn: () => listDepartments({ pageSize: 100, ordering: "name", isActive: true }),
    staleTime: 60_000,
  });
}
