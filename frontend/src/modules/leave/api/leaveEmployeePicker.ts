import { API_ENDPOINTS } from "@/lib/api/endpoints";
import { httpClient } from "@/lib/api/httpClient";
import type { ApiSuccessResponse } from "@/lib/api/types";
import type { LeaveEmployeeOption } from "@/modules/leave/types/leave.types";

interface EmployeeWireResponseForPicker {
  id: string;
  full_name: string;
  employee_code: string;
}

/**
 * A narrow, module-local fetch against `GET /api/v1/employees/` — only the
 * few fields "Apply Leave for Employee" / "Adjust Balance" need to pick an
 * employee, not the full `EmployeeResponseSerializer` shape
 * `modules/employees` works with. Deliberately duplicated rather than
 * importing `modules/employees` or `modules/users`' own equivalent —
 * matches the precedent `modules/users/api/userApi.ts`'s
 * `searchEmployeesForLinking` docstring already establishes: a small
 * per-module copy of "search employees for a picker" keeps every module
 * independent of the others, at the (accepted) cost of this one small
 * duplication.
 */
export async function searchActiveEmployees(search: string): Promise<LeaveEmployeeOption[]> {
  const response = await httpClient.get<ApiSuccessResponse<EmployeeWireResponseForPicker[]>>(
    `${API_ENDPOINTS.employees}/`,
    { params: { search: search || undefined, employment_status: "active", page_size: 25, ordering: "first_name,last_name" } },
  );
  return response.data.data.map((wire) => ({
    id: wire.id,
    fullName: wire.full_name,
    employeeCode: wire.employee_code,
  }));
}
