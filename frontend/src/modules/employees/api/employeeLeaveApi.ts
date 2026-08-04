/**
 * A narrow, per-module fetch against Leave's already-existing employee-
 * scoped endpoints (`GET /leave/balance/{employee_id}/`,
 * `GET /leave/requests/employee/{employee_id}/` — both already gated by
 * `leave.view_leave` on the backend, unchanged by this file). Deliberately
 * NOT imported from `modules/leave` — this module keeps its own narrow
 * copy of "what does this employee's leave look like," the same
 * "small per-module duplication over cross-module import" precedent
 * `modules/leave/api/leaveEmployeePicker.ts` already established (there,
 * Leave duplicated a slice of Employees' data instead of importing
 * Employees' own picker component; here it's the same trade-off running
 * in the other direction — Employees duplicating a slice of Leave's data
 * rather than importing Leave's richer types/components). Employees is the
 * more foundational module; it must never depend on a feature module built
 * on top of it.
 */
import { API_ENDPOINTS } from "@/lib/api/endpoints";
import { httpClient } from "@/lib/api/httpClient";
import type { ApiSuccessResponse, PagedResult } from "@/lib/api/types";
import type {
  EmployeeLeaveBalance,
  EmployeeLeaveHistoryFilters,
  EmployeeLeaveRequest,
} from "@/modules/employees/types/employeeLeave.types";

interface EmployeeLeaveBalanceWireResponse {
  leave_type_id: string;
  leave_type_name: string | null;
  entitled_days: string;
  used_days: string;
  carried_forward_days: string;
  available_days: string;
  pending_days: string;
}

interface EmployeeLeaveRequestWireResponse {
  id: string;
  leave_type_name: string | null;
  start_date: string;
  end_date: string;
  total_days: string;
  working_days: string;
  status: string;
}

function toEmployeeLeaveBalance(wire: EmployeeLeaveBalanceWireResponse): EmployeeLeaveBalance {
  return {
    leaveTypeId: wire.leave_type_id,
    leaveTypeName: wire.leave_type_name,
    entitledDays: wire.entitled_days,
    usedDays: wire.used_days,
    carriedForwardDays: wire.carried_forward_days,
    availableDays: wire.available_days,
    pendingDays: wire.pending_days,
  };
}

function toEmployeeLeaveRequest(wire: EmployeeLeaveRequestWireResponse): EmployeeLeaveRequest {
  return {
    id: wire.id,
    leaveTypeName: wire.leave_type_name,
    startDate: wire.start_date,
    endDate: wire.end_date,
    totalDays: wire.total_days,
    workingDays: wire.working_days,
    status: wire.status as EmployeeLeaveRequest["status"],
  };
}

/** `GET /api/v1/leave/balance/{employee_id}/?year=` — requires leave.view_leave. */
export async function getEmployeeLeaveBalance(
  employeeId: string,
  year?: number,
): Promise<EmployeeLeaveBalance[]> {
  const response = await httpClient.get<ApiSuccessResponse<EmployeeLeaveBalanceWireResponse[]>>(
    `${API_ENDPOINTS.leave}/balance/${employeeId}/`,
    { params: { year } },
  );
  return response.data.data.map(toEmployeeLeaveBalance);
}

/** `GET /api/v1/leave/requests/employee/{employee_id}/` — requires leave.view_leave. */
export async function listEmployeeLeaveHistory(
  employeeId: string,
  filters: EmployeeLeaveHistoryFilters = {},
): Promise<PagedResult<EmployeeLeaveRequest>> {
  const response = await httpClient.get<ApiSuccessResponse<EmployeeLeaveRequestWireResponse[]>>(
    `${API_ENDPOINTS.leave}/requests/employee/${employeeId}/`,
    { params: { page: filters.page, page_size: filters.pageSize } },
  );
  return { items: response.data.data.map(toEmployeeLeaveRequest), meta: response.data.meta! };
}
