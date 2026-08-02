import { ArrowLeft } from "lucide-react";
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState, PageHeader, PageLoader } from "@/components/common";
import { ROUTE_PATHS } from "@/app/router/routePaths";
import { ApiError } from "@/lib/api/types";
import { useCurrentUserQuery } from "@/lib/auth";
import { ApprovalHistoryPanel, SUBJECT_TYPE_LEAVE_REQUEST } from "@/modules/approvals";
import { CancelLeaveDialog } from "@/modules/leave/components/CancelLeaveDialog";
import { LeaveStatusBadge } from "@/modules/leave/components/LeaveStatusBadge";
import { useCancelLeaveForEmployeeMutation, useCancelLeaveMutation } from "@/modules/leave/hooks/useLeaveMutations";
import { useEmployeeLeaveBalanceQuery, useLeaveRequestDetailQuery } from "@/modules/leave/hooks/useLeaveQueries";

const CANCELLABLE_STATUSES = new Set(["pending", "approved"]);

/** View Leave Details (Phase 13) — "/leave/:id". Shows the request itself
 * plus its full approval history (delegated to the Approvals module's own
 * `ApprovalHistoryPanel` — see that component's docstring for why this is
 * the sanctioned cross-module dependency direction). */
export function LeaveRequestDetailPage() {
  const { leaveRequestId } = useParams<{ leaveRequestId: string }>();
  const navigate = useNavigate();
  const { data: currentUser } = useCurrentUserQuery();
  const canManage = currentUser?.permissionCodes.includes("leave.manage_leave") ?? false;

  const { data: request, isLoading, isError, refetch } = useLeaveRequestDetailQuery(leaveRequestId);
  const cancelMutation = useCancelLeaveMutation();
  const cancelForEmployeeMutation = useCancelLeaveForEmployeeMutation();
  // Round 14 item 2 — "current leave balances for all leave types," shown
  // alongside the balance-at-application snapshot below. Fetched only once
  // `request` resolves (needs its employeeId), same enabled-gating pattern
  // as this hook's other callers.
  const currentBalanceQuery = useEmployeeLeaveBalanceQuery(request?.employeeId);

  const [cancelling, setCancelling] = useState(false);
  const [cancelError, setCancelError] = useState<string | null>(null);

  if (isLoading) {
    return <PageLoader label="Loading leave request…" />;
  }
  if (isError || !request) {
    return (
      <ErrorState
        title="Couldn't load this leave request"
        onRetry={() => {
          void refetch();
        }}
      />
    );
  }

  const isOwnRequest = currentUser?.employeeId === request.employeeId;
  const canCancel = CANCELLABLE_STATUSES.has(request.status) && (isOwnRequest || canManage);

  const handleCancelConfirm = (cancellationReason: string | null) => {
    setCancelError(null);
    const onSettled = {
      onSuccess: () => {
        toast.success("Leave request cancelled.");
        setCancelling(false);
      },
      onError: (error: unknown) => {
        setCancelError(error instanceof ApiError ? error.message : "Could not cancel this request.");
      },
    };
    if (!isOwnRequest && canManage) {
      cancelForEmployeeMutation.mutate({ leaveRequestId: request.id, input: { cancellationReason } }, onSettled);
    } else {
      cancelMutation.mutate({ leaveRequestId: request.id, input: { cancellationReason } }, onSettled);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Leave Request"
        description={request.leaveTypeName ?? "Leave"}
        actions={
          <>
            <Button variant="ghost" onClick={() => navigate(ROUTE_PATHS.dashboard.leave)}>
              <ArrowLeft className="size-4" aria-hidden="true" />
              Back to Leave
            </Button>
            {canCancel ? (
              <Button variant="destructive" onClick={() => setCancelling(true)}>
                Cancel Request
              </Button>
            ) : null}
          </>
        }
      />

      <Card>
        <CardContent className="grid gap-4 pt-6 sm:grid-cols-2">
          <div>
            <p className="text-xs text-muted-foreground">Status</p>
            <LeaveStatusBadge status={request.status} />
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Dates</p>
            <p className="text-sm text-foreground">
              {request.startDate} → {request.endDate}
            </p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Total days applied</p>
            <p className="text-sm text-foreground">{request.totalDays} day(s)</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Working days applied</p>
            <p className="text-sm text-foreground">
              {request.workingDays} day(s)
              <span className="ml-1 text-xs text-muted-foreground">
                (excludes week-off and holidays — balance is deducted using this figure)
              </span>
            </p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Leave balance at time of application</p>
            <p className="text-sm text-foreground">{request.balanceAtApplication} day(s) available</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Reason</p>
            <p className="text-sm text-foreground">{request.reason ?? "—"}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Decision comments</p>
            <p className="text-sm text-foreground">{request.decisionComments ?? "—"}</p>
          </div>
          {request.cancelledAt ? (
            <div className="sm:col-span-2">
              <p className="text-xs text-muted-foreground">Cancellation reason</p>
              <p className="text-sm text-foreground">{request.cancellationReason ?? "—"}</p>
            </div>
          ) : null}
        </CardContent>
      </Card>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold text-foreground">Current leave balances</h2>
        {currentBalanceQuery.isLoading ? (
          <PageLoader label="Loading current balances…" />
        ) : currentBalanceQuery.isError ? (
          <ErrorState
            title="Couldn't load current leave balances"
            onRetry={() => {
              void currentBalanceQuery.refetch();
            }}
          />
        ) : currentBalanceQuery.data && currentBalanceQuery.data.length > 0 ? (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {currentBalanceQuery.data.map((balance) => (
              <Card key={balance.leaveTypeId}>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm">{balance.leaveTypeName ?? "Leave"}</CardTitle>
                </CardHeader>
                <CardContent className="space-y-1">
                  <p className="text-xl font-semibold text-foreground">
                    {balance.availableDays}
                    <span className="ml-1 text-xs font-normal text-muted-foreground">days available</span>
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Entitled {balance.entitledDays} · Used {balance.usedDays} · Pending {balance.pendingDays}
                  </p>
                </CardContent>
              </Card>
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">No leave balance data yet.</p>
        )}
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold text-foreground">Approval status</h2>
        <ApprovalHistoryPanel subjectType={SUBJECT_TYPE_LEAVE_REQUEST} subjectId={request.id} />
      </section>

      <CancelLeaveDialog
        open={cancelling}
        onOpenChange={setCancelling}
        leaveRequest={request}
        onConfirm={handleCancelConfirm}
        isSubmitting={cancelMutation.isPending || cancelForEmployeeMutation.isPending}
        submitError={cancelError}
      />
    </div>
  );
}
