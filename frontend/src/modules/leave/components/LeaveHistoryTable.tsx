import { useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { buildLeaveRequestDetailPath } from "@/app/router/routePaths";
import { LeaveStatusBadge } from "@/modules/leave/components/LeaveStatusBadge";
import type { LeaveRequest } from "@/modules/leave/types/leave.types";

interface LeaveHistoryTableProps {
  requests: LeaveRequest[];
  onCancel?: (request: LeaveRequest) => void;
  /** Shows an "Employee" column (name + code) — used only by the HR-wide
   * "manage" queue (Phase 13 review requirement), where `request.employeeName`/
   * `employeeCode` are actually populated; every other caller of this table
   * is already scoped to one employee and leaves this off. */
  showEmployeeColumn?: boolean;
}

const CANCELLABLE_STATUSES = new Set(["pending", "approved"]);

export function LeaveHistoryTable({ requests, onCancel, showEmployeeColumn = false }: LeaveHistoryTableProps) {
  const navigate = useNavigate();

  return (
    <Table>
      <TableHeader>
        <TableRow>
          {showEmployeeColumn ? <TableHead>Employee</TableHead> : null}
          <TableHead>Leave Type</TableHead>
          <TableHead>Dates</TableHead>
          <TableHead>Total Days</TableHead>
          <TableHead>Working Days</TableHead>
          <TableHead>Status</TableHead>
          <TableHead className="text-right">Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {requests.map((request) => (
          <TableRow key={request.id}>
            {showEmployeeColumn ? (
              <TableCell>
                <div className="font-medium text-foreground">{request.employeeName ?? "—"}</div>
                <div className="text-xs text-muted-foreground">{request.employeeCode ?? ""}</div>
              </TableCell>
            ) : null}
            <TableCell>{request.leaveTypeName ?? "—"}</TableCell>
            <TableCell>
              {request.startDate} → {request.endDate}
            </TableCell>
            <TableCell>{request.totalDays}</TableCell>
            <TableCell>{request.workingDays}</TableCell>
            <TableCell>
              <LeaveStatusBadge status={request.status} />
            </TableCell>
            <TableCell className="text-right">
              <div className="flex justify-end gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => navigate(buildLeaveRequestDetailPath(request.id))}
                >
                  View
                </Button>
                {onCancel && CANCELLABLE_STATUSES.has(request.status) ? (
                  <Button variant="ghost" size="sm" onClick={() => onCancel(request)}>
                    Cancel
                  </Button>
                ) : null}
              </div>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
