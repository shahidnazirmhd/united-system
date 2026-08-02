import { API_ENDPOINTS } from "@/lib/api/endpoints";
import { httpClient } from "@/lib/api/httpClient";
import type { ApiSuccessResponse, PagedResult } from "@/lib/api/types";
import type {
  AdjustLeaveBalanceInput,
  ApplyLeaveInput,
  CancelLeaveInput,
  CreateLeaveTypeInput,
  LeaveBalance,
  LeaveBalanceAdjustment,
  LeaveHistoryFilters,
  LeaveRequest,
  LeaveType,
  LeaveTypeListFilters,
  ManageLeaveRequestsFilters,
  UpdateLeaveTypeInput,
} from "@/modules/leave/types/leave.types";

/** The exact wire shapes LEAVE_API.md documents. */
interface LeaveTypeWireResponse {
  id: string;
  name: string;
  code: string;
  default_annual_days: string;
  is_paid: boolean;
  requires_approval: boolean;
  is_active: boolean;
}

interface LeaveBalanceWireResponse {
  employee_id: string;
  leave_type_id: string;
  leave_type_name: string | null;
  year: number;
  entitled_days: string;
  used_days: string;
  carried_forward_days: string;
  available_days: string;
  pending_days: string;
}

interface LeaveRequestWireResponse {
  id: string;
  employee_id: string;
  leave_type_id: string;
  leave_type_name: string | null;
  start_date: string;
  end_date: string;
  total_days: string;
  working_days: string;
  balance_at_application: string;
  reason: string | null;
  status: string;
  approved_by: string | null;
  decided_at: string | null;
  decision_comments: string | null;
  cancelled_at: string | null;
  cancellation_reason: string | null;
  // Populated only on the HR-wide "manage" list (Phase 13 review
  // requirement) — null on every other read.
  employee_name: string | null;
  employee_code: string | null;
}

interface LeaveBalanceAdjustmentWireResponse {
  id: string;
  employee_id: string;
  leave_type_id: string;
  year: number;
  adjustment_type: string;
  previous_entitled_days: string;
  previous_used_days: string;
  previous_carried_forward_days: string;
  new_entitled_days: string;
  new_used_days: string;
  new_carried_forward_days: string;
  reason: string;
  adjusted_by: string | null;
  created_at: string;
}

function toLeaveType(wire: LeaveTypeWireResponse): LeaveType {
  return {
    id: wire.id,
    name: wire.name,
    code: wire.code,
    defaultAnnualDays: wire.default_annual_days,
    isPaid: wire.is_paid,
    requiresApproval: wire.requires_approval,
    isActive: wire.is_active,
  };
}

function toLeaveBalance(wire: LeaveBalanceWireResponse): LeaveBalance {
  return {
    employeeId: wire.employee_id,
    leaveTypeId: wire.leave_type_id,
    leaveTypeName: wire.leave_type_name,
    year: wire.year,
    entitledDays: wire.entitled_days,
    usedDays: wire.used_days,
    carriedForwardDays: wire.carried_forward_days,
    availableDays: wire.available_days,
    pendingDays: wire.pending_days,
  };
}

function toLeaveRequest(wire: LeaveRequestWireResponse): LeaveRequest {
  return {
    id: wire.id,
    employeeId: wire.employee_id,
    leaveTypeId: wire.leave_type_id,
    leaveTypeName: wire.leave_type_name,
    startDate: wire.start_date,
    endDate: wire.end_date,
    totalDays: wire.total_days,
    workingDays: wire.working_days,
    balanceAtApplication: wire.balance_at_application,
    reason: wire.reason,
    status: wire.status as LeaveRequest["status"],
    approvedBy: wire.approved_by,
    decidedAt: wire.decided_at,
    decisionComments: wire.decision_comments,
    cancelledAt: wire.cancelled_at,
    cancellationReason: wire.cancellation_reason,
    employeeName: wire.employee_name,
    employeeCode: wire.employee_code,
  };
}

function toLeaveBalanceAdjustment(wire: LeaveBalanceAdjustmentWireResponse): LeaveBalanceAdjustment {
  return {
    id: wire.id,
    employeeId: wire.employee_id,
    leaveTypeId: wire.leave_type_id,
    year: wire.year,
    adjustmentType: wire.adjustment_type as LeaveBalanceAdjustment["adjustmentType"],
    previousEntitledDays: wire.previous_entitled_days,
    previousUsedDays: wire.previous_used_days,
    previousCarriedForwardDays: wire.previous_carried_forward_days,
    newEntitledDays: wire.new_entitled_days,
    newUsedDays: wire.new_used_days,
    newCarriedForwardDays: wire.new_carried_forward_days,
    reason: wire.reason,
    adjustedBy: wire.adjusted_by,
    createdAt: wire.created_at,
  };
}

// --- Leave Types ------------------------------------------------------

/** `GET /api/v1/leave/types/` — active only, every apply-leave dropdown. */
export async function listActiveLeaveTypes(): Promise<LeaveType[]> {
  const response = await httpClient.get<ApiSuccessResponse<LeaveTypeWireResponse[]>>(
    `${API_ENDPOINTS.leave}/types/`,
  );
  return response.data.data.map(toLeaveType);
}

/** `GET /api/v1/leave/types/manage/` — Leave Type Management admin listing. */
export async function listLeaveTypesForManagement(
  filters: LeaveTypeListFilters = {},
): Promise<PagedResult<LeaveType>> {
  const response = await httpClient.get<ApiSuccessResponse<LeaveTypeWireResponse[]>>(
    `${API_ENDPOINTS.leave}/types/manage/`,
    {
      params: {
        is_active: filters.isActive,
        search: filters.search || undefined,
        page: filters.page,
        page_size: filters.pageSize,
      },
    },
  );
  return { items: response.data.data.map(toLeaveType), meta: response.data.meta! };
}

/** `POST /api/v1/leave/types/manage/` */
export async function createLeaveType(input: CreateLeaveTypeInput): Promise<LeaveType> {
  const response = await httpClient.post<ApiSuccessResponse<LeaveTypeWireResponse>>(
    `${API_ENDPOINTS.leave}/types/manage/`,
    {
      name: input.name,
      code: input.code,
      default_annual_days: input.defaultAnnualDays,
      is_paid: input.isPaid,
      requires_approval: input.requiresApproval,
    },
  );
  return toLeaveType(response.data.data);
}

/** `PATCH /api/v1/leave/types/manage/{id}/` */
export async function updateLeaveType(leaveTypeId: string, input: UpdateLeaveTypeInput): Promise<LeaveType> {
  const response = await httpClient.patch<ApiSuccessResponse<LeaveTypeWireResponse>>(
    `${API_ENDPOINTS.leave}/types/manage/${leaveTypeId}/`,
    {
      name: input.name,
      code: input.code,
      default_annual_days: input.defaultAnnualDays,
      is_paid: input.isPaid,
      requires_approval: input.requiresApproval,
      is_active: input.isActive,
    },
  );
  return toLeaveType(response.data.data);
}

// --- Leave Balance ------------------------------------------------------

/** `GET /api/v1/leave/balance/me/?year=` */
export async function getMyLeaveBalance(year?: number): Promise<LeaveBalance[]> {
  const response = await httpClient.get<ApiSuccessResponse<LeaveBalanceWireResponse[]>>(
    `${API_ENDPOINTS.leave}/balance/me/`,
    { params: { year } },
  );
  return response.data.data.map(toLeaveBalance);
}

/** `GET /api/v1/leave/balance/{employee_id}/?year=` — requires leave.view_leave. */
export async function getEmployeeLeaveBalance(employeeId: string, year?: number): Promise<LeaveBalance[]> {
  const response = await httpClient.get<ApiSuccessResponse<LeaveBalanceWireResponse[]>>(
    `${API_ENDPOINTS.leave}/balance/${employeeId}/`,
    { params: { year } },
  );
  return response.data.data.map(toLeaveBalance);
}

/** `POST /api/v1/leave/balances/adjust/` — requires leave.manage_leave. One
 * upsert path backs both Leave Balance Opening and Adjustment. */
export async function adjustLeaveBalance(input: AdjustLeaveBalanceInput): Promise<LeaveBalanceAdjustment> {
  const response = await httpClient.post<ApiSuccessResponse<LeaveBalanceAdjustmentWireResponse>>(
    `${API_ENDPOINTS.leave}/balances/adjust/`,
    {
      employee_id: input.employeeId,
      leave_type_id: input.leaveTypeId,
      year: input.year,
      entitled_days: input.entitledDays,
      used_days: input.usedDays,
      carried_forward_days: input.carriedForwardDays,
      reason: input.reason,
    },
  );
  return toLeaveBalanceAdjustment(response.data.data);
}

// --- Leave Requests ------------------------------------------------------

/** `GET /api/v1/leave/requests/` — the caller's own history. */
export async function listMyLeaveHistory(filters: LeaveHistoryFilters = {}): Promise<PagedResult<LeaveRequest>> {
  const response = await httpClient.get<ApiSuccessResponse<LeaveRequestWireResponse[]>>(
    `${API_ENDPOINTS.leave}/requests/`,
    { params: { status: filters.status, page: filters.page, page_size: filters.pageSize } },
  );
  return { items: response.data.data.map(toLeaveRequest), meta: response.data.meta! };
}

/** `GET /api/v1/leave/requests/employee/{employee_id}/` — requires leave.view_leave. */
export async function listEmployeeLeaveHistory(
  employeeId: string,
  filters: LeaveHistoryFilters = {},
): Promise<PagedResult<LeaveRequest>> {
  const response = await httpClient.get<ApiSuccessResponse<LeaveRequestWireResponse[]>>(
    `${API_ENDPOINTS.leave}/requests/employee/${employeeId}/`,
    { params: { status: filters.status, page: filters.page, page_size: filters.pageSize } },
  );
  return { items: response.data.data.map(toLeaveRequest), meta: response.data.meta! };
}

/** `GET /api/v1/leave/requests/{id}/` */
export async function getLeaveRequestById(leaveRequestId: string): Promise<LeaveRequest> {
  const response = await httpClient.get<ApiSuccessResponse<LeaveRequestWireResponse>>(
    `${API_ENDPOINTS.leave}/requests/${leaveRequestId}/`,
  );
  return toLeaveRequest(response.data.data);
}

/** `POST /api/v1/leave/requests/` — apply on the caller's own behalf. */
export async function applyLeave(input: ApplyLeaveInput): Promise<LeaveRequest> {
  const response = await httpClient.post<ApiSuccessResponse<LeaveRequestWireResponse>>(
    `${API_ENDPOINTS.leave}/requests/`,
    { leave_type_id: input.leaveTypeId, start_date: input.startDate, end_date: input.endDate, reason: input.reason ?? null },
  );
  return toLeaveRequest(response.data.data);
}

/** `POST /api/v1/leave/requests/employee/{employee_id}/apply/` — HR/Admin
 * applies on a named employee's behalf. Requires leave.manage_leave. */
export async function applyLeaveForEmployee(employeeId: string, input: ApplyLeaveInput): Promise<LeaveRequest> {
  const response = await httpClient.post<ApiSuccessResponse<LeaveRequestWireResponse>>(
    `${API_ENDPOINTS.leave}/requests/employee/${employeeId}/apply/`,
    { leave_type_id: input.leaveTypeId, start_date: input.startDate, end_date: input.endDate, reason: input.reason ?? null },
  );
  return toLeaveRequest(response.data.data);
}

/** `POST /api/v1/leave/requests/{id}/cancel/` — the caller's own request. */
export async function cancelLeaveRequest(leaveRequestId: string, input: CancelLeaveInput = {}): Promise<LeaveRequest> {
  const response = await httpClient.post<ApiSuccessResponse<LeaveRequestWireResponse>>(
    `${API_ENDPOINTS.leave}/requests/${leaveRequestId}/cancel/`,
    { cancellation_reason: input.cancellationReason ?? null },
  );
  return toLeaveRequest(response.data.data);
}

/** `POST /api/v1/leave/requests/{id}/cancel-for-employee/` — HR/Admin
 * cancels any employee's request. Requires leave.manage_leave. */
export async function cancelLeaveRequestForEmployee(
  leaveRequestId: string,
  input: CancelLeaveInput = {},
): Promise<LeaveRequest> {
  const response = await httpClient.post<ApiSuccessResponse<LeaveRequestWireResponse>>(
    `${API_ENDPOINTS.leave}/requests/${leaveRequestId}/cancel-for-employee/`,
    { cancellation_reason: input.cancellationReason ?? null },
  );
  return toLeaveRequest(response.data.data);
}

/** `GET /api/v1/leave/requests/manage/` — every leave request across every
 * employee (Phase 13 review requirement) — requires leave.view_leave.
 * Backs the Leave module's HR-only processing queue; every filter is
 * optional. */
export async function listAllLeaveRequestsAdmin(
  filters: ManageLeaveRequestsFilters = {},
): Promise<PagedResult<LeaveRequest>> {
  const response = await httpClient.get<ApiSuccessResponse<LeaveRequestWireResponse[]>>(
    `${API_ENDPOINTS.leave}/requests/manage/`,
    {
      params: {
        employee_id: filters.employeeId,
        status: filters.status,
        leave_type_id: filters.leaveTypeId,
        start_date_from: filters.startDateFrom,
        start_date_to: filters.startDateTo,
        page: filters.page,
        page_size: filters.pageSize,
      },
    },
  );
  return { items: response.data.data.map(toLeaveRequest), meta: response.data.meta! };
}
