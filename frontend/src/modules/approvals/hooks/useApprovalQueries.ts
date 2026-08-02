import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import { createQueryKeyFactory } from "@/lib/api";
import type { ApiError } from "@/lib/api/types";
import {
  getApprovalRequestById,
  listApprovalHistoryForSubject,
  listMyPendingApprovals,
} from "@/modules/approvals/api/approvalApi";
import type { ApprovalRequest } from "@/modules/approvals/types/approval.types";

export const approvalKeys = createQueryKeyFactory<string>("approvals");

/** "My Pending Approvals" inbox — short staleTime, this is the one screen
 * in the app most likely to go stale while the user is looking at it (a
 * peer manager could decide the same request first in a multi-approver
 * future, or a new one could arrive). */
export function useMyPendingApprovalsQuery(): UseQueryResult<ApprovalRequest[], ApiError> {
  return useQuery({
    queryKey: approvalKeys.list("pending-me"),
    queryFn: listMyPendingApprovals,
    staleTime: 15_000,
  });
}

export function useApprovalRequestDetailQuery(approvalRequestId: string | undefined) {
  return useQuery({
    queryKey: approvalKeys.detail(approvalRequestId ?? ""),
    queryFn: () => getApprovalRequestById(approvalRequestId as string),
    enabled: Boolean(approvalRequestId),
  });
}

/** Backs Leave Request Detail's approval-history panel — see
 * `listApprovalHistoryForSubject`'s own docstring for why an empty result
 * is a normal, non-error outcome. */
export function useApprovalHistoryBySubjectQuery(subjectType: string, subjectId: string | undefined) {
  return useQuery({
    queryKey: [...approvalKeys.all, "by-subject", subjectType, subjectId ?? ""] as const,
    queryFn: () => listApprovalHistoryForSubject(subjectType, subjectId as string),
    enabled: Boolean(subjectId),
  });
}
