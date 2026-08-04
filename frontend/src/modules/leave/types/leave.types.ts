/**
 * This module's own domain types — never imported by the foundation, same
 * rule every other module's own types file documents. Field names/shape
 * mirror LEAVE_API.md's response serializers exactly, camelCased.
 */
export type LeaveRequestStatus = "draft" | "pending" | "approved" | "rejected" | "cancelled";

export const LEAVE_REQUEST_STATUS_OPTIONS: { value: LeaveRequestStatus; label: string }[] = [
  { value: "pending", label: "Pending" },
  { value: "approved", label: "Approved" },
  { value: "rejected", label: "Rejected" },
  { value: "cancelled", label: "Cancelled" },
];

/** Which Employee Current Status an approved request of this leave type
 * drives while it's in progress — mirrors the backend's
 * `domain/employee_status_mapping.py.ALLOWED_EMPLOYEE_STATUS_MAPPINGS`
 * exactly. `null` means this leave type never changes Current Status at
 * all (e.g. an unpaid leave type HR doesn't want reflected there). */
export type LeaveTypeStatusMapping = "sick_leave" | "annual_leave" | null;

export const LEAVE_TYPE_STATUS_MAPPING_OPTIONS: {
  value: NonNullable<LeaveTypeStatusMapping>;
  label: string;
}[] = [
  { value: "sick_leave", label: "Sick Leave" },
  { value: "annual_leave", label: "Annual Leave" },
];

export interface LeaveType {
  id: string;
  name: string;
  code: string;
  defaultAnnualDays: string;
  isPaid: boolean;
  requiresApproval: boolean;
  isActive: boolean;
  mapsToEmployeeStatus: LeaveTypeStatusMapping;
}

export interface LeaveBalance {
  employeeId: string;
  leaveTypeId: string;
  leaveTypeName: string | null;
  year: number;
  entitledDays: string;
  usedDays: string;
  carriedForwardDays: string;
  availableDays: string;
  pendingDays: string;
}

export interface LeaveRequest {
  id: string;
  employeeId: string;
  leaveTypeId: string;
  leaveTypeName: string | null;
  startDate: string;
  endDate: string;
  totalDays: string;
  /** Round 14 item 6 — calendar days excluding the configured week-off and
   * holidays; balance is deducted/restored using this figure, not totalDays. */
  workingDays: string;
  /** Round 14 item 2 — a snapshot of `availableDays` for this leave type
   * taken at the moment this request was applied (before any deduction). */
  balanceAtApplication: string;
  reason: string | null;
  status: LeaveRequestStatus;
  approvedBy: string | null;
  decidedAt: string | null;
  decisionComments: string | null;
  cancelledAt: string | null;
  cancellationReason: string | null;
  // Populated only by the HR-wide "manage" list (Phase 13 review
  // requirement) — null on every other read, which already has employee
  // context from the caller.
  employeeName: string | null;
  employeeCode: string | null;
  // --- HR Leave Workflow round (skip-level-1 + initiator tracking) -------
  level1Skipped: boolean;
  /** e.g. "no_manager_assigned" / "manager_not_linked_to_telegram" — see
   * `LEVEL1_SKIP_REASON_LABELS` below for the display string. */
  level1SkipReason: string | null;
  /** Which channel submitted this request — `"hr"` (an HR/Admin user
   * applying on an employee's behalf) or `"telegram"` (the employee
   * themself, via the bot). `null` for ordinary self-service web apply —
   * no special "initiated by" block is shown for that case. */
  initiatedVia: "hr" | "telegram" | null;
  initiatorUserId: string | null;
  initiatorTelegramUserId: number | null;
  /** Resolved display name for `initiatedVia === "hr"` only, e.g.
   * "Jane Doe (E0031)". `null` for `"telegram"` (show the raw
   * `initiatorTelegramUserId` instead) or ordinary self-service. */
  initiatorDisplayName: string | null;
}

/** HR Leave Workflow round, item 1 — user-facing copy for each
 * `level1SkipReason` code the backend may send, reused verbatim wherever
 * the skip is displayed (Leave Details, Leave History, the pre-submit
 * confirmation dialog). Falls back to the raw code itself if a future
 * backend reason isn't in this map yet, rather than showing nothing. */
export const LEVEL1_SKIP_REASON_LABELS: Record<string, string> = {
  no_manager_assigned: "No manager assigned",
  manager_not_linked_to_telegram: "Manager has not linked their Telegram account",
};

/** HR Leave Workflow round, item 1 — backs the pre-submit confirmation
 * dialog's preview call (`GET .../level1-approval-check/`). */
export interface Level1ApprovalCheck {
  willSkipLevel1: boolean;
  skipReason: string | null;
}

export interface LeaveHistoryFilters {
  status?: LeaveRequestStatus;
  page?: number;
  pageSize?: number;
}

// --- HR-wide leave request queue (Phase 13 review requirement) -----------
// The Leave module tab processes applications across every employee — it
// is no longer a personal "my leave" view (that moved to Employee
// Details' own Leave section, see modules/employees/api/employeeLeaveApi.ts).
export interface ManageLeaveRequestsFilters {
  employeeId?: string;
  status?: LeaveRequestStatus;
  leaveTypeId?: string;
  startDateFrom?: string;
  startDateTo?: string;
  page?: number;
  pageSize?: number;
}

export interface ApplyLeaveInput {
  leaveTypeId: string;
  startDate: string;
  endDate: string;
  reason?: string | null;
}

export interface CancelLeaveInput {
  cancellationReason?: string | null;
}

// --- Leave Type Management (Phase 13, leave.manage_leave) -----------------

export interface LeaveTypeListFilters {
  isActive?: boolean;
  search?: string;
  page?: number;
  pageSize?: number;
}

export interface CreateLeaveTypeInput {
  name: string;
  code: string;
  defaultAnnualDays: string;
  isPaid: boolean;
  requiresApproval: boolean;
  mapsToEmployeeStatus: LeaveTypeStatusMapping;
}

export interface UpdateLeaveTypeInput extends CreateLeaveTypeInput {
  isActive: boolean;
}

// --- Leave Balance Adjustment / Opening (Phase 13, leave.manage_leave) ----

export type LeaveBalanceAdjustmentType = "opening" | "adjustment";

export interface AdjustLeaveBalanceInput {
  employeeId: string;
  leaveTypeId: string;
  year: number;
  entitledDays: string;
  usedDays: string;
  carriedForwardDays: string;
  reason: string;
}

export interface LeaveBalanceAdjustment {
  id: string;
  employeeId: string;
  leaveTypeId: string;
  year: number;
  adjustmentType: LeaveBalanceAdjustmentType;
  previousEntitledDays: string;
  previousUsedDays: string;
  previousCarriedForwardDays: string;
  newEntitledDays: string;
  newUsedDays: string;
  newCarriedForwardDays: string;
  reason: string;
  adjustedBy: string | null;
  createdAt: string;
}

// --- This module's own small employee-search picker (Phase 13) -----------
// Deliberately a separate, narrower shape from modules/employees' full
// `Employee` type and from modules/users' own `LinkableEmployee` — see
// api/leaveEmployeePicker.ts's docstring for why this module keeps its own
// copy of this small fetch instead of importing either.
export interface LeaveEmployeeOption {
  id: string;
  fullName: string;
  employeeCode: string;
}
