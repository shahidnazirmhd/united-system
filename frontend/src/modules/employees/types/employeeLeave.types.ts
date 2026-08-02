/**
 * A deliberately small, read-only slice of Leave's data — just enough to
 * show an employee's balance/history on their own Employee Details page
 * (Phase 13 review requirement: "Leave module tab" moved to
 * processing-only; personal leave data belongs here instead). A separate
 * shape from `modules/leave`'s own richer `LeaveBalance`/`LeaveRequest`
 * types on purpose — this module never imports from `modules/leave` (see
 * `api/employeeLeaveApi.ts`'s docstring for the full "keep modules
 * independent" reasoning, the same precedent `modules/leave`'s own
 * employee-picker already established, just running in the other
 * direction this time).
 */
export type EmployeeLeaveRequestStatus = "draft" | "pending" | "approved" | "rejected" | "cancelled";

export interface EmployeeLeaveBalance {
  leaveTypeId: string;
  leaveTypeName: string | null;
  entitledDays: string;
  usedDays: string;
  carriedForwardDays: string;
  availableDays: string;
  pendingDays: string;
}

export interface EmployeeLeaveRequest {
  id: string;
  leaveTypeName: string | null;
  startDate: string;
  endDate: string;
  totalDays: string;
  /** Round 15 item 2 — calendar days excluding week-off/holidays. */
  workingDays: string;
  status: EmployeeLeaveRequestStatus;
}

export interface EmployeeLeaveHistoryFilters {
  page?: number;
  pageSize?: number;
}
