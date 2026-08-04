import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import { createQueryKeyFactory } from "@/lib/api";
import type { ApiError, PagedResult } from "@/lib/api/types";
import {
  checkLevel1ApprovalSkip,
  getEmployeeLeaveBalance,
  getLeaveRequestById,
  getMyLeaveBalance,
  listActiveLeaveTypes,
  listAllLeaveRequestsAdmin,
  listEmployeeLeaveHistory,
  listMyLeaveHistory,
} from "@/modules/leave/api/leaveApi";
import { searchActiveEmployees } from "@/modules/leave/api/leaveEmployeePicker";
import type {
  Level1ApprovalCheck,
  LeaveBalance,
  LeaveEmployeeOption,
  LeaveHistoryFilters,
  LeaveRequest,
  LeaveType,
  ManageLeaveRequestsFilters,
} from "@/modules/leave/types/leave.types";

export const leaveKeys = createQueryKeyFactory<LeaveHistoryFilters>("leave");

export function useLeaveTypesQuery(): UseQueryResult<LeaveType[], ApiError> {
  return useQuery({
    queryKey: [...leaveKeys.all, "types"] as const,
    queryFn: listActiveLeaveTypes,
    staleTime: 60_000,
  });
}

export function useMyLeaveBalanceQuery(year?: number): UseQueryResult<LeaveBalance[], ApiError> {
  return useQuery({
    queryKey: [...leaveKeys.all, "balance", "me", year ?? "current"] as const,
    queryFn: () => getMyLeaveBalance(year),
  });
}

export function useEmployeeLeaveBalanceQuery(
  employeeId: string | undefined,
  year?: number,
): UseQueryResult<LeaveBalance[], ApiError> {
  return useQuery({
    queryKey: [...leaveKeys.all, "balance", employeeId ?? "", year ?? "current"] as const,
    queryFn: () => getEmployeeLeaveBalance(employeeId as string, year),
    enabled: Boolean(employeeId),
  });
}

export function useMyLeaveHistoryQuery(
  filters: LeaveHistoryFilters,
): UseQueryResult<PagedResult<LeaveRequest>, ApiError> {
  return useQuery({
    queryKey: leaveKeys.list(filters),
    queryFn: () => listMyLeaveHistory(filters),
    placeholderData: (previousData) => previousData,
  });
}

export function useEmployeeLeaveHistoryQuery(
  employeeId: string | undefined,
  filters: LeaveHistoryFilters,
): UseQueryResult<PagedResult<LeaveRequest>, ApiError> {
  return useQuery({
    queryKey: [...leaveKeys.all, "list", "employee", employeeId ?? "", filters] as const,
    queryFn: () => listEmployeeLeaveHistory(employeeId as string, filters),
    enabled: Boolean(employeeId),
    placeholderData: (previousData) => previousData,
  });
}

export function useLeaveRequestDetailQuery(
  leaveRequestId: string | undefined,
): UseQueryResult<LeaveRequest, ApiError> {
  return useQuery({
    queryKey: leaveKeys.detail(leaveRequestId ?? ""),
    queryFn: () => getLeaveRequestById(leaveRequestId as string),
    enabled: Boolean(leaveRequestId),
  });
}

/** Feeds "Apply Leave for Employee" / "Adjust Balance"'s search-as-you-type
 * employee picker — see api/leaveEmployeePicker.ts's docstring. */
export function useActiveEmployeeSearchQuery(
  search: string,
): UseQueryResult<LeaveEmployeeOption[], ApiError> {
  return useQuery({
    queryKey: [...leaveKeys.all, "employee-search", search] as const,
    queryFn: () => searchActiveEmployees(search),
    staleTime: 30_000,
  });
}

/** HR Leave Workflow round, item 1 — backs the HR-on-behalf Apply Leave
 * dialog's pre-submit confirmation step. Only meaningful for that flow, so
 * callers pass `undefined` (disabling the query) for self-service apply. */
export function useLevel1ApprovalCheckQuery(
  employeeId: string | undefined,
): UseQueryResult<Level1ApprovalCheck, ApiError> {
  return useQuery({
    queryKey: [...leaveKeys.all, "level1-approval-check", employeeId ?? ""] as const,
    queryFn: () => checkLevel1ApprovalSkip(employeeId as string),
    enabled: Boolean(employeeId),
    staleTime: 10_000,
  });
}

/** HR-wide leave request queue (Phase 13 review requirement) — every
 * employee's requests, filterable. Backs the Leave module's now
 * HR-only-processing Dashboard (see pages/LeaveDashboardPage.tsx's
 * docstring for why this replaced the old "my own leave" view). */
export function useManageLeaveRequestsQuery(
  filters: ManageLeaveRequestsFilters,
): UseQueryResult<PagedResult<LeaveRequest>, ApiError> {
  return useQuery({
    queryKey: [...leaveKeys.all, "manage-list", filters] as const,
    queryFn: () => listAllLeaveRequestsAdmin(filters),
    placeholderData: (previousData) => previousData,
  });
}
