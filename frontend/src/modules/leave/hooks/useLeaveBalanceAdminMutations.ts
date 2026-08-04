import { useMutation, useQueryClient, type UseMutationResult } from "@tanstack/react-query";

import type { ApiError } from "@/lib/api/types";
import { adjustLeaveBalance } from "@/modules/leave/api/leaveApi";
import { leaveKeys } from "@/modules/leave/hooks/useLeaveQueries";
import type {
  AdjustLeaveBalanceInput,
  LeaveBalanceAdjustment,
} from "@/modules/leave/types/leave.types";

/** Backs both "Leave Balance Adjustment" and "Leave Balance Opening" —
 * one API call, two UI entry points (see BalanceAdjustmentDialog.tsx). */
export function useAdjustLeaveBalanceMutation(): UseMutationResult<
  LeaveBalanceAdjustment,
  ApiError,
  AdjustLeaveBalanceInput
> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: adjustLeaveBalance,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: leaveKeys.all });
    },
  });
}
