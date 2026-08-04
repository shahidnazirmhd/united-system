import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { ErrorState, PageLoader } from "@/components/common";
import { ApiError } from "@/lib/api/types";
import { useCurrentUserQuery } from "@/lib/auth";
import { ApprovalStatusBadge } from "@/modules/approvals/components/ApprovalStatusBadge";
import { DecideApprovalDialog } from "@/modules/approvals/components/DecideApprovalDialog";
import { useDecideApprovalMutation } from "@/modules/approvals/hooks/useApprovalMutations";
import { useApprovalHistoryBySubjectQuery } from "@/modules/approvals/hooks/useApprovalQueries";
import {
  APPROVAL_CHANNEL_TELEGRAM,
  APPROVAL_CHANNEL_WEB,
  type ApprovalDecision,
  type ApprovalRequest,
} from "@/modules/approvals/types/approval.types";

interface ApprovalHistoryPanelProps {
  subjectType: string;
  subjectId: string;
}

/**
 * Whether the currently logged-in employee may decide `request`'s current
 * level right now — mirrors the backend's own `ApprovalStep.is_decidable_by`
 * rule exactly (see apps/approvals/domain/entities.py): a step assigned to
 * one specific employee only that employee can act on; a step assigned by
 * permission code (Phase 13 — e.g. Leave's HR/Admin level) any employee
 * currently holding that code can act on.
 *
 * Approval Workflow Changes review round: ALSO mirrors
 * `ApprovalStep.is_decidable_via_channel` — a step restricted to Telegram
 * (e.g. a future module's Telegram-only level) can never be decided from
 * here, this being the web app, regardless of who's looking at it. This is
 * a defense-in-depth UI hint only; the backend enforces the real gate
 * (`approval_channel_not_allowed`) on the decide endpoint itself.
 *
 * Approval Workflow Changes v2: ALSO mirrors the dual-mode branch of
 * `ApprovalStep.is_decidable_by` — a step with BOTH `approverEmployeeId`
 * AND `approverPermissionCode` set (e.g. Leave's level 1: the manager via
 * Telegram, any `approvals.level1_approve` holder via the web) is governed,
 * on the web channel specifically, by `permissionRequiredForChannel`: if
 * that equals "web", holding the permission is what matters here, NOT
 * being the referenced employee — even for the manager themselves. Since
 * this app only ever operates as the web channel, this branch never needs
 * to consider the Telegram side of a dual-mode step at all (the backend
 * enforces that half).
 */
function isDecidableByCurrentUser(
  request: ApprovalRequest,
  currentEmployeeId: string | null,
  heldPermissionCodes: string[],
): boolean {
  if (request.status !== "pending") return false;
  const currentStep = request.steps.find((step) => step.level === request.currentLevel);
  if (!currentStep || currentStep.status !== "pending") return false;
  if (currentStep.restrictedToChannel === APPROVAL_CHANNEL_TELEGRAM) return false;
  if (currentStep.approverEmployeeId && currentStep.approverPermissionCode) {
    // Dual-mode: on the web, the permission governs when this is the
    // channel it's required for — identity is irrelevant here in that case.
    if (currentStep.permissionRequiredForChannel === APPROVAL_CHANNEL_WEB) {
      return heldPermissionCodes.includes(currentStep.approverPermissionCode);
    }
    return currentStep.approverEmployeeId === currentEmployeeId;
  }
  if (currentStep.approverEmployeeId) return currentStep.approverEmployeeId === currentEmployeeId;
  if (currentStep.approverPermissionCode)
    return heldPermissionCodes.includes(currentStep.approverPermissionCode);
  return false;
}

/** A `for_employee` step's approver, described relative to its own status
 * — "Awaiting decision from …" while pending, "Approved by …"/"Rejected
 * by …" once decided. Generic: this component never learns the approver
 * is "a manager," it only ever has a name/code to show (Approval Workflow
 * Changes review round — satisfies "display Level 1 approval status:
 * pending with manager name and employee code; if approved, show approved
 * by manager name and employee code," for any `for_employee` level of any
 * subject module, not just Leave's). `null` for a permission-based step,
 * which has no single employee to name. */
function approverDisplayLine(step: ApprovalRequest["steps"][number]): string | null {
  if (!step.approverEmployeeName) return null;
  const who = step.approverEmployeeCode
    ? `${step.approverEmployeeName} (${step.approverEmployeeCode})`
    : step.approverEmployeeName;
  if (step.status === "approved") return `Approved by ${who}`;
  if (step.status === "rejected") return `Rejected by ${who}`;
  // Round 17 item 2 — the request was cancelled by the subject module (the
  // requester withdrew it), not decided by `who` — worth saying explicitly
  // rather than falling through to "Awaiting decision", which would be
  // actively wrong once nothing is being awaited any more.
  if (step.status === "cancelled")
    return `No longer needed — the request was cancelled (was awaiting ${who})`;
  return `Awaiting decision from ${who}`;
}

/**
 * Approval history/timeline for one subject — the reusable piece behind
 * Leave Request Detail's "Approval status" section (Phase 13). Exported
 * from this module's public barrel so a subject module (Leave today, any
 * future one) can drop it into its own detail page without duplicating the
 * fetch/render logic — the Approval Engine stays the one place that knows
 * how to display its own step history.
 *
 * Also lets the current employee decide the request's current level right
 * here, inline, if `isDecidableByCurrentUser` says they qualify (Phase 13
 * addition) — this benefits every subject module that embeds this
 * component, not just Leave, and avoids forcing an HR/Admin reviewer to
 * leave the Leave Request Detail page and go find the same request again
 * in the generic "My Pending Approvals" inbox.
 */
export function ApprovalHistoryPanel({ subjectType, subjectId }: ApprovalHistoryPanelProps) {
  const { data, isLoading, isError, refetch } = useApprovalHistoryBySubjectQuery(
    subjectType,
    subjectId,
  );
  const { data: currentUser } = useCurrentUserQuery();
  const decideMutation = useDecideApprovalMutation();
  const [decidingRequestId, setDecidingRequestId] = useState<string | null>(null);
  const [decideError, setDecideError] = useState<string | null>(null);

  if (isLoading) {
    return <PageLoader label="Loading approval history…" />;
  }
  if (isError) {
    return (
      <ErrorState
        title="Couldn't load approval history"
        onRetry={() => {
          void refetch();
        }}
      />
    );
  }
  if (!data || data.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">No approval history for this request yet.</p>
    );
  }

  const decidingRequest = data.find((request) => request.id === decidingRequestId);

  const handleDecide = (decision: ApprovalDecision, comments: string | null) => {
    if (!decidingRequestId) return;
    setDecideError(null);
    decideMutation.mutate(
      { approvalRequestId: decidingRequestId, input: { decision, comments } },
      {
        onSuccess: () => {
          toast.success(decision === "approve" ? "Approval recorded." : "Rejection recorded.");
          setDecidingRequestId(null);
        },
        onError: (error) => {
          setDecideError(
            error instanceof ApiError ? error.message : "Could not record this decision.",
          );
        },
      },
    );
  };

  return (
    <div className="space-y-4">
      {data.map((approvalRequest) => {
        const canDecide = isDecidableByCurrentUser(
          approvalRequest,
          currentUser?.employeeId ?? null,
          currentUser?.permissionCodes ?? [],
        );
        return (
          <div key={approvalRequest.id} className="rounded-lg border border-border p-4">
            <div className="mb-3 flex items-center justify-between">
              <span className="text-sm font-medium text-foreground">Approval request</span>
              <div className="flex items-center gap-2">
                <ApprovalStatusBadge status={approvalRequest.status} />
                {canDecide ? (
                  <Button size="sm" onClick={() => setDecidingRequestId(approvalRequest.id)}>
                    Decide
                  </Button>
                ) : null}
              </div>
            </div>
            <ol className="space-y-3">
              {approvalRequest.steps.map((step) => {
                const approverLine = approverDisplayLine(step);
                return (
                  <li key={step.id} className="flex items-start justify-between gap-4 text-sm">
                    <div>
                      <div className="font-medium text-foreground">Level {step.level}</div>
                      {approverLine ? (
                        <p className="mt-1 text-muted-foreground">{approverLine}</p>
                      ) : null}
                      {step.comments ? (
                        <p className="mt-1 text-muted-foreground">&ldquo;{step.comments}&rdquo;</p>
                      ) : null}
                      {step.decidedAt ? (
                        <p className="mt-1 text-xs text-muted-foreground">
                          Decided {new Date(step.decidedAt).toLocaleString()}
                        </p>
                      ) : null}
                    </div>
                    <ApprovalStatusBadge status={step.status} />
                  </li>
                );
              })}
            </ol>
          </div>
        );
      })}

      <DecideApprovalDialog
        open={decidingRequestId !== null}
        onOpenChange={(open) => {
          if (!open) setDecidingRequestId(null);
        }}
        approvalRequest={decidingRequest}
        onDecide={handleDecide}
        isSubmitting={decideMutation.isPending}
        submitError={decideError}
      />
    </div>
  );
}
