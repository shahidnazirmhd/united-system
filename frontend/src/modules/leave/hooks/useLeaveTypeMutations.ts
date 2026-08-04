import { useMutation, useQueryClient, type UseMutationResult } from "@tanstack/react-query";

import type { ApiError } from "@/lib/api/types";
import { createLeaveType, updateLeaveType } from "@/modules/leave/api/leaveApi";
import { leaveKeys } from "@/modules/leave/hooks/useLeaveQueries";
import type {
  CreateLeaveTypeInput,
  LeaveType,
  UpdateLeaveTypeInput,
} from "@/modules/leave/types/leave.types";

export function useCreateLeaveTypeMutation(): UseMutationResult<
  LeaveType,
  ApiError,
  CreateLeaveTypeInput
> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createLeaveType,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: leaveKeys.all });
    },
  });
}

export function useUpdateLeaveTypeMutation(): UseMutationResult<
  LeaveType,
  ApiError,
  { leaveTypeId: string; input: UpdateLeaveTypeInput }
> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ leaveTypeId, input }) => updateLeaveType(leaveTypeId, input),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: leaveKeys.all });
    },
  });
}
