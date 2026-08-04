import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { Badge, type BadgeProps } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Pagination } from "@/components/ui/pagination";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ErrorState, PageLoader } from "@/components/common";
import { buildLeaveRequestDetailPath } from "@/app/router/routePaths";
import {
  useEmployeeLeaveBalanceQuery,
  useEmployeeLeaveHistoryQuery,
} from "@/modules/employees/hooks/useEmployeeLeaveQueries";
import type {
  EmployeeLeaveHistoryFilters,
  EmployeeLeaveRequestStatus,
} from "@/modules/employees/types/employeeLeave.types";

const STATUS_VARIANT: Record<EmployeeLeaveRequestStatus, NonNullable<BadgeProps["variant"]>> = {
  draft: "secondary",
  pending: "warning",
  approved: "success",
  rejected: "destructive",
  cancelled: "secondary",
};

const STATUS_LABEL: Record<EmployeeLeaveRequestStatus, string> = {
  draft: "Draft",
  pending: "Pending",
  approved: "Approved",
  rejected: "Rejected",
  cancelled: "Cancelled",
};

const DEFAULT_FILTERS: EmployeeLeaveHistoryFilters = { page: 1, pageSize: 5 };

interface EmployeeLeaveSectionProps {
  employeeId: string;
}

/**
 * Employee Details' own Leave section (Phase 13 review requirement) — a
 * read-only balance + recent-history view for this one employee, replacing
 * the personal leave view that used to live on the Leave module tab. Built
 * entirely from this module's own narrow `employeeLeaveApi.ts` fetch, not
 * from `modules/leave`'s components — see that file's docstring for why.
 */
export function EmployeeLeaveSection({ employeeId }: EmployeeLeaveSectionProps) {
  const navigate = useNavigate();
  const [filters, setFilters] = useState<EmployeeLeaveHistoryFilters>(DEFAULT_FILTERS);

  const balanceQuery = useEmployeeLeaveBalanceQuery(employeeId);
  const historyQuery = useEmployeeLeaveHistoryQuery(employeeId, filters);

  return (
    <div className="space-y-4">
      <div>
        <h2 className="mb-3 text-lg font-semibold text-foreground">Leave Balance</h2>
        {balanceQuery.isLoading ? (
          <PageLoader label="Loading balance…" />
        ) : balanceQuery.isError ? (
          <ErrorState
            title="Couldn't load leave balance"
            onRetry={() => {
              void balanceQuery.refetch();
            }}
          />
        ) : balanceQuery.data && balanceQuery.data.length > 0 ? (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {balanceQuery.data.map((balance) => (
              <Card key={balance.leaveTypeId}>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm">{balance.leaveTypeName ?? "Leave"}</CardTitle>
                </CardHeader>
                <CardContent className="space-y-1">
                  <p className="text-xl font-semibold text-foreground">
                    {balance.availableDays}
                    <span className="ml-1 text-xs font-normal text-muted-foreground">
                      days available
                    </span>
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Entitled {balance.entitledDays} · Used {balance.usedDays} · Pending{" "}
                    {balance.pendingDays}
                  </p>
                </CardContent>
              </Card>
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">No leave balance data yet.</p>
        )}
      </div>

      <div>
        <h2 className="mb-3 text-lg font-semibold text-foreground">Leave History</h2>
        {historyQuery.isLoading ? (
          <PageLoader label="Loading leave history…" />
        ) : historyQuery.isError ? (
          <ErrorState
            title="Couldn't load leave history"
            onRetry={() => {
              void historyQuery.refetch();
            }}
          />
        ) : historyQuery.data && historyQuery.data.items.length > 0 ? (
          <div className="rounded-lg border border-border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Leave Type</TableHead>
                  <TableHead>Dates</TableHead>
                  <TableHead>Total Days</TableHead>
                  <TableHead>Working Days</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {historyQuery.data.items.map((request) => (
                  <TableRow
                    key={request.id}
                    className="cursor-pointer"
                    onClick={() => navigate(buildLeaveRequestDetailPath(request.id))}
                  >
                    <TableCell>{request.leaveTypeName ?? "—"}</TableCell>
                    <TableCell>
                      {request.startDate} → {request.endDate}
                    </TableCell>
                    <TableCell>{request.totalDays}</TableCell>
                    <TableCell>{request.workingDays}</TableCell>
                    <TableCell>
                      <Badge variant={STATUS_VARIANT[request.status]}>
                        {STATUS_LABEL[request.status]}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <Pagination
              page={historyQuery.data.meta.page}
              totalPages={historyQuery.data.meta.total_pages}
              totalCount={historyQuery.data.meta.total_count}
              pageSize={historyQuery.data.meta.page_size}
              onPageChange={(page) => setFilters((current) => ({ ...current, page }))}
            />
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">No leave requests yet.</p>
        )}
      </div>
    </div>
  );
}
