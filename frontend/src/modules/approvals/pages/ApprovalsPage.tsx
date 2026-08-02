import { ClipboardCheck } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { EmptyState, ErrorState, PageHeader, PageLoader } from "@/components/common";
import { ApiError } from "@/lib/api/types";
import { DecideApprovalDialog } from "@/modules/approvals/components/DecideApprovalDialog";
import { ApprovalTable } from "@/modules/approvals/components/ApprovalTable";
import { useDecideApprovalMutation } from "@/modules/approvals/hooks/useApprovalMutations";
import { useMyPendingApprovalsQuery } from "@/modules/approvals/hooks/useApprovalQueries";
import type { ApprovalDecision, ApprovalRequest } from "@/modules/approvals/types/approval.types";

/**
 * My Pending Approvals (Phase 13) — every approval request currently
 * awaiting a decision from the caller, across every subject module (Leave
 * today; any future module with zero changes to this page, matching the
 * backend endpoint's own subject-agnostic design). No search/filter/
 * pagination here: this is deliberately "your immediate inbox," not a
 * browsable list — `GET /approvals/pending/me/` is unpaginated for the
 * same reason.
 */
export function ApprovalsPage() {
  const { data, isLoading, isError, refetch } = useMyPendingApprovalsQuery();
  const decideMutation = useDecideApprovalMutation();

  const [deciding, setDeciding] = useState<ApprovalRequest | undefined>(undefined);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const handleDecide = (decision: ApprovalDecision, comments: string | null) => {
    if (!deciding) return;
    setSubmitError(null);
    decideMutation.mutate(
      { approvalRequestId: deciding.id, input: { decision, comments } },
      {
        onSuccess: () => {
          toast.success(decision === "approve" ? "Request approved." : "Request rejected.");
          setDeciding(undefined);
        },
        onError: (error) => {
          if (error instanceof ApiError) {
            setSubmitError(error.message);
          } else {
            setSubmitError("Could not record this decision.");
          }
        },
      },
    );
  };

  return (
    <div>
      <PageHeader
        title="Approvals"
        description="Requests from every module currently awaiting your decision."
      />

      {isLoading ? (
        <PageLoader label="Loading pending approvals…" />
      ) : isError ? (
        <ErrorState
          title="Couldn't load pending approvals"
          onRetry={() => {
            void refetch();
          }}
        />
      ) : data && data.length > 0 ? (
        <div className="rounded-lg border border-border">
          <ApprovalTable approvalRequests={data} onDecide={setDeciding} />
        </div>
      ) : (
        <EmptyState
          icon={ClipboardCheck}
          title="Nothing waiting on you"
          description="Requests assigned to you for approval will show up here."
        />
      )}

      <DecideApprovalDialog
        open={Boolean(deciding)}
        onOpenChange={(open) => !open && setDeciding(undefined)}
        approvalRequest={deciding}
        onDecide={handleDecide}
        isSubmitting={decideMutation.isPending}
        submitError={submitError}
      />
    </div>
  );
}
