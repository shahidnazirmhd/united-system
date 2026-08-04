import { useMutation, useQueryClient, type UseMutationResult } from "@tanstack/react-query";

import type { ApiError } from "@/lib/api/types";
import { decideApprovalRequest } from "@/modules/approvals/api/approvalApi";
import { approvalKeys } from "@/modules/approvals/hooks/useApprovalQueries";
import type {
  ApprovalRequest,
  DecideApprovalInput,
} from "@/modules/approvals/types/approval.types";

export function useDecideApprovalMutation(): UseMutationResult<
  ApprovalRequest,
  ApiError,
  { approvalRequestId: string; input: DecideApprovalInput }
> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ approvalRequestId, input }) => decideApprovalRequest(approvalRequestId, input),
    onSuccess: () => {
      // The whole "approvals" namespace, not just lists()/detail() —
      // ApprovalHistoryPanel's by-subject query lives under this same
      // prefix (see useApprovalHistoryBySubjectQuery) and must refetch too
      // now that this component can decide inline, not just the
      // dedicated Approvals inbox page.
      void queryClient.invalidateQueries({ queryKey: approvalKeys.all });
      // A decided leave request's status/approval history changed — Leave's
      // own list/detail/balance views should refetch too. Cross-module
      // invalidation by query-key namespace only (never a cross-module
      // import), same precedent useLinkUserToEmployeeMutation established.
      void queryClient.invalidateQueries({ queryKey: ["leave"] });
    },
  });
}
