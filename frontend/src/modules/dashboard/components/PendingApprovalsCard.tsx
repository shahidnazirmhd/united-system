import { ClipboardCheck } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { ROUTE_PATHS } from "@/app/router/routePaths";
import { Button } from "@/components/ui/button";
import { DashboardWidgetCard } from "@/modules/dashboard/components/DashboardWidgetCard";
import { useMyPendingApprovalsQuery } from "@/modules/approvals/hooks/useApprovalQueries";

/**
 * Pending Approvals widget — deliberately reuses Approvals' own
 * `useMyPendingApprovalsQuery` hook (already built for the Approvals
 * module's own inbox page) rather than adding a new backend endpoint or
 * frontend query for what is, underneath, the exact same "my pending
 * approvals" read. No `useHasPermission` gate here (unlike every other
 * Dashboard widget): approving/rejecting is available to whoever the
 * Approval Engine actually assigned as a step's approver, which isn't a
 * static permission code this widget could check up front — the query
 * itself simply returns an empty list for a caller with nothing pending,
 * which the empty state below already handles.
 */
export function PendingApprovalsCard() {
  const navigate = useNavigate();
  const { data, isLoading, isError, refetch } = useMyPendingApprovalsQuery();

  return (
    <DashboardWidgetCard
      title="Pending Approvals"
      icon={ClipboardCheck}
      isLoading={isLoading}
      isError={isError}
      onRetry={() => void refetch()}
      isEmpty={(data ?? []).length === 0}
      emptyTitle="Nothing waiting on you"
      emptyDescription="Requests assigned to you for approval will appear here."
    >
      <ul className="divide-y divide-border">
        {(data ?? []).slice(0, 5).map((request) => (
          <li key={request.id} className="flex items-center justify-between gap-3 py-2.5 first:pt-0 last:pb-0">
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-foreground">{request.subjectSummary}</p>
              <p className="text-xs text-muted-foreground">Level {request.currentLevel}</p>
            </div>
            <Button variant="outline" size="sm" onClick={() => navigate(ROUTE_PATHS.dashboard.approvals)}>
              Review
            </Button>
          </li>
        ))}
      </ul>
      {(data ?? []).length > 5 ? (
        <Button
          variant="link"
          size="sm"
          className="mt-2 h-auto px-0"
          onClick={() => navigate(ROUTE_PATHS.dashboard.approvals)}
        >
          View all {data?.length} pending approvals
        </Button>
      ) : null}
    </DashboardWidgetCard>
  );
}
