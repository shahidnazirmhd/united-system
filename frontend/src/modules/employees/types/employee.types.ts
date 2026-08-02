/**
 * This module's own domain types — never imported by the foundation, same
 * rule `modules/auth/types/auth.types.ts` documents. Field names/shape
 * mirror EMPLOYEE_API.md's `EmployeeResponseSerializer` exactly, camelCased.
 */
export type EmployeeStatus = "active" | "on_leave" | "suspended" | "terminated";
export type EmploymentType = "full_time" | "part_time" | "contract" | "intern";

/**
 * Round 14 item 8 — a second, HR-visible "day-to-day work status" field,
 * deliberately separate from `EmployeeStatus` above (which governs system
 * access — activate/deactivate/Telegram linking). See the backend's
 * `EmployeeCurrentStatus` enum docstring for the full reasoning.
 */
export type EmployeeCurrentStatus =
  | "not_joined"
  | "working"
  | "sick_leave"
  | "annual_leave"
  | "terminated"
  | "resigned";

/** Manually settable values only — Sick Leave/Annual Leave are system-managed
 * by the Leave module and deliberately excluded, mirroring the backend's
 * `UpdateEmployeeCurrentStatusSerializer` choice list exactly. */
export const MANUAL_CURRENT_STATUS_OPTIONS: { value: EmployeeCurrentStatus; label: string }[] = [
  { value: "not_joined", label: "Not Joined" },
  { value: "working", label: "Working" },
  { value: "terminated", label: "Terminated" },
  { value: "resigned", label: "Resigned" },
];

export const CURRENT_STATUS_LABELS: Record<EmployeeCurrentStatus, string> = {
  not_joined: "Not Joined",
  working: "Working",
  sick_leave: "Sick Leave",
  annual_leave: "Annual Leave",
  terminated: "Terminated",
  resigned: "Resigned",
};

export const EMPLOYEE_STATUS_OPTIONS: { value: EmployeeStatus; label: string }[] = [
  { value: "active", label: "Active" },
  { value: "on_leave", label: "On Leave" },
  { value: "suspended", label: "Suspended" },
  { value: "terminated", label: "Terminated" },
];

export const EMPLOYMENT_TYPE_OPTIONS: { value: EmploymentType; label: string }[] = [
  { value: "full_time", label: "Full-time" },
  { value: "part_time", label: "Part-time" },
  { value: "contract", label: "Contract" },
  { value: "intern", label: "Intern" },
];

export interface Employee {
  id: string;
  employeeCode: string;
  userId: string | null;
  firstName: string;
  lastName: string;
  fullName: string;
  dateOfBirth: string | null;
  gender: string | null;
  workEmail: string;
  personalEmail: string | null;
  phoneNumber: string | null;
  departmentId: string;
  managerId: string | null;
  jobTitle: string;
  employmentType: EmploymentType;
  dateOfJoining: string;
  /** Round 15 item 9 — renamed from terminationDate; used for both resignation and termination. */
  lastWorkingDate: string | null;
  status: EmployeeStatus;
  /** Resolved on single-record reads only — null on list/search rows. */
  departmentName: string | null;
  managerName: string | null;
  /** Phase 12 bugfix: email of the linked identity.User, same scope as the two fields above. */
  linkedUserEmail: string | null;
  isLinkedToTelegram: boolean;
  telegramUsername: string | null;
  telegramLinkedAt: string | null;
  currentStatus: EmployeeCurrentStatus;
  statusBeforeLeave: EmployeeCurrentStatus | null;
  isEligibleForLeave: boolean;
}

export interface EmployeeListFilters {
  departmentId?: string;
  employmentStatus?: EmployeeStatus;
  employmentType?: EmploymentType;
  search?: string;
  ordering?: string;
  page?: number;
  pageSize?: number;
}

export interface CreateEmployeeInput {
  firstName: string;
  lastName: string;
  dateOfBirth: string | null;
  gender: string | null;
  workEmail: string;
  personalEmail: string | null;
  phoneNumber: string | null;
  departmentId: string;
  managerId: string | null;
  jobTitle: string;
  employmentType: EmploymentType;
  dateOfJoining: string;
  userId: string | null;
}

export interface UpdateEmployeeInput {
  firstName: string;
  lastName: string;
  dateOfBirth: string | null;
  gender: string | null;
  workEmail: string;
  personalEmail: string | null;
  phoneNumber: string | null;
  departmentId: string;
  managerId: string | null;
  jobTitle: string;
  employmentType: EmploymentType;
  dateOfJoining: string;
  /** Round 15 item 9 — renamed from terminationDate; used for both resignation and termination. */
  lastWorkingDate: string | null;
}
