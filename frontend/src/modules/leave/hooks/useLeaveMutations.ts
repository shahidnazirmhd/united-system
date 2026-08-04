import { useMutation, useQueryClient, type UseMutationResult } from "@tanstack/react-query";

import type { ApiError } from "@/lib/api/types";
import {
  applyLeave,
  applyLeaveForEmployee,
  cancelLeaveRequest,
  cancelLeaveRequestForEmployee,
} from "@/modules/leave/api/leaveApi";
import { leaveKeys } from "@/modules/leave/hooks/useLeaveQueries";
import type {
  ApplyLeaveInput,
  CancelLeaveInput,
  LeaveRequest,
} from "@/modules/leave/types/leave.types";

function invalidateLeave(queryClient: ReturnType<typeof useQueryClient>) {
  void queryClient.invalidateQueries({ queryKey: leaveKeys.all });
}

export function useApplyLeaveMutation(): UseMutationResult<
  LeaveRequest,
  ApiError,
  ApplyLeaveInput
> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: applyLeave,
    onSuccess: () => invalidateLeave(queryClient),
  });
}

export function useApplyLeaveForEmployeeMutation(): UseMutationResult<
  LeaveRequest,
  ApiError,
  { employeeId: string; input: ApplyLeaveInput }
> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ employeeId, input }) => applyLeaveForEmployee(employeeId, input),
    onSuccess: () => invalidateLeave(queryClient),
  });
}

export function useCancelLeaveMutation(): UseMutationResult<
  LeaveRequest,
  ApiError,
  { leaveRequestId: string; input?: CancelLeaveInput }
> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ leaveRequestId, input }) => cancelLeaveRequest(leaveRequestId, input),
    onSuccess: () => invalidateLeave(queryClient),
  });
}

export function useCancelLeaveForEmployeeMutation(): UseMutationResult<
  LeaveRequest,
  ApiError,
  { leaveRequestId: string; input?: CancelLeaveInput }
> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ leaveRequestId, input }) => cancelLeaveRequestForEmployee(leaveRequestId, input),
    onSuccess: () => invalidateLeave(queryClient),
  });
}
