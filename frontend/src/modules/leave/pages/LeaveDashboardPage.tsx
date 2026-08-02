import { Lock, Plus, Settings, Sliders, X } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Pagination } from "@/components/ui/pagination";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { EmptyState, ErrorState, PageHeader, PageLoader } from "@/components/common";
import { ROUTE_PATHS } from "@/app/router/routePaths";
import { useCurrentUserQuery } from "@/lib/auth";
import { ApiError } from "@/lib/api/types";
import { ApplyLeaveDialog } from "@/modules/leave/components/ApplyLeaveDialog";
import { BalanceAdjustmentDialog } from "@/modules/leave/components/BalanceAdjustmentDialog";
import { LeaveEmployeePickerField } from "@/modules/leave/components/LeaveEmployeePickerField";
import { LeaveHistoryTable } from "@/modules/leave/components/LeaveHistoryTable";
import { useAdjustLeaveBalanceMutation } from "@/modules/leave/hooks/useLeaveBalanceAdminMutations";
import { useApplyLeaveForEmployeeMutation } from "@/modules/leave/hooks/useLeaveMutations";
import { useLeaveTypesQuery, useManageLeaveRequestsQuery } from "@/modules/leave/hooks/useLeaveQueries";
import type { ApplyLeaveFormValues } from "@/modules/leave/validation/applyLeaveSchema";
import type { BalanceAdjustmentFormValues } from "@/modules/leave/validation/balanceAdjustmentSchema";
import type {
  LeaveEmployeeOption,
  ManageLeaveRequestsFilters,
  LeaveRequestStatus,
} from "@/modules/leave/types/leave.types";

const ALL_STATUS = "__all__";
const ALL_TYPE = "__all__";
const DEFAULT_FILTERS: ManageLeaveRequestsFilters = { page: 1, pageSize: 25 };

/**
 * Leave Dashboard (Phase 13, redesigned per the review requirement) — the
 * "/leave" entry point. Deliberately no longer shows the logged-in user's
 * own leave balance/history/apply/cancel — this tab is HR/Admin's
 * processing queue for leave applications across every employee, nothing
 * more. An employee's own leave data now lives on their Employee Details
 * page (see modules/employees' own Leave section); employees keep
 * applying/viewing their leave entirely through Telegram, unchanged.
 *
 * Access is gated on `leave.view_leave`/`leave.manage_leave` client-side
 * (an `EmptyState` explaining the restriction, matching this codebase's
 * existing "sidebar always visible, page itself decides access" pattern —
 * no route-level permission guard exists yet for any module) — the
 * backend enforces the real gate regardless.
 */
export function LeaveDashboardPage() {
  const navigate = useNavigate();
  const { data: currentUser } = useCurrentUserQuery();
  const canManage = currentUser?.permissionCodes.includes("leave.manage_leave") ?? false;
  const canView = canManage || (currentUser?.permissionCodes.includes("leave.view_leave") ?? false);

  const [filterEmployee, setFilterEmployee] = useState<LeaveEmployeeOption | null>(null);
  const [filters, setFilters] = useState<ManageLeaveRequestsFilters>(DEFAULT_FILTERS);

  const effectiveFilters: ManageLeaveRequestsFilters = { ...filters, employeeId: filterEmployee?.id };
  const { data: leaveTypes } = useLeaveTypesQuery();
  const requestsQuery = useManageLeaveRequestsQuery(effectiveFilters);

  const applyForEmployeeMutation = useApplyLeaveForEmployeeMutation();
  const adjustBalanceMutation = useAdjustLeaveBalanceMutation();

  const [applyDialogOpen, setApplyDialogOpen] = useState(false);
  const [applyError, setApplyError] = useState<string | null>(null);
  const [balanceDialog, setBalanceDialog] = useState<"open" | "adjust" | null>(null);
  const [balanceError, setBalanceError] = useState<string | null>(null);

  if (!canView) {
    return (
      <div>
        <PageHeader title="Leave Management" description="Review and process leave applications." />
        <EmptyState
          icon={Lock}
          title="You don't have access to Leave Management"
          description="This area is for HR/Admin leave processing. Ask an administrator for the leave.view_leave permission if you believe this is a mistake."
        />
      </div>
    );
  }

  const handleApplySubmit = (values: ApplyLeaveFormValues, employee: LeaveEmployeeOption | null) => {
    setApplyError(null);
    if (!employee) {
      setApplyError("Pick an employee to apply this leave for.");
      return;
    }
    applyForEmployeeMutation.mutate(
      {
        employeeId: employee.id,
        input: {
          leaveTypeId: values.leaveTypeId,
          startDate: values.startDate,
          endDate: values.endDate,
          reason: values.reason,
        },
      },
      {
        onSuccess: (result) => {
          // Round 14 item 6 — surface both figures at the moment of
          // application; the Leave Details page shows them permanently.
          toast.success(
            `Leave application submitted: ${result.totalDays} day(s) total, ${result.workingDays} working day(s).`,
          );
          setApplyDialogOpen(false);
        },
        onError: (error: unknown) => {
          setApplyError(error instanceof ApiError ? error.message : "Could not submit this application.");
        },
      },
    );
  };

  const handleBalanceSubmit = (values: BalanceAdjustmentFormValues) => {
    setBalanceError(null);
    adjustBalanceMutation.mutate(
      {
        employeeId: values.employeeId,
        leaveTypeId: values.leaveTypeId,
        year: Number(values.year),
        entitledDays: values.entitledDays,
        usedDays: values.usedDays,
        carriedForwardDays: values.carriedForwardDays,
        reason: values.reason,
      },
      {
        onSuccess: (result) => {
          toast.success(
            result.adjustmentType === "opening" ? "Leave balance opened." : "Leave balance adjusted.",
          );
          setBalanceDialog(null);
        },
        onError: (error) => {
          setBalanceError(error instanceof ApiError ? error.message : "Could not save this balance change.");
        },
      },
    );
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Leave Management"
        description="Review and process leave applications across every employee."
        actions={
          <>
            {canManage ? (
              <Button variant="ghost" onClick={() => navigate(ROUTE_PATHS.dashboard.leaveTypes)}>
                <Settings className="size-4" aria-hidden="true" />
                Leave Types
              </Button>
            ) : null}
            {canManage ? (
              <Button variant="ghost" onClick={() => setBalanceDialog("open")}>
                <Sliders className="size-4" aria-hidden="true" />
                Open Balance
              </Button>
            ) : null}
            {canManage ? (
              <Button variant="ghost" onClick={() => setBalanceDialog("adjust")}>
                <Sliders className="size-4" aria-hidden="true" />
                Adjust Balance
              </Button>
            ) : null}
            {canManage ? (
              <Button onClick={() => setApplyDialogOpen(true)}>
                <Plus className="size-4" aria-hidden="true" />
                Apply for Employee
              </Button>
            ) : null}
          </>
        }
      />

      <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center">
        <div className="w-full sm:max-w-xs">
          {filterEmployee ? (
            <div className="flex items-center justify-between rounded-md border border-border px-3 py-2 text-sm">
              <div>
                <div className="font-medium text-foreground">{filterEmployee.fullName}</div>
                <div className="text-xs text-muted-foreground">{filterEmployee.employeeCode}</div>
              </div>
              <button
                type="button"
                onClick={() => setFilterEmployee(null)}
                className="rounded p-1 text-muted-foreground hover:bg-accent hover:text-foreground"
                aria-label="Clear employee filter"
              >
                <X className="size-4" aria-hidden="true" />
              </button>
            </div>
          ) : (
            <LeaveEmployeePickerField selected={filterEmployee} onSelect={setFilterEmployee} />
          )}
        </div>

        <Select
          value={filters.status ?? ALL_STATUS}
          onValueChange={(value) =>
            setFilters((current) => ({
              ...current,
              status: value === ALL_STATUS ? undefined : (value as LeaveRequestStatus),
              page: 1,
            }))
          }
        >
          <SelectTrigger className="w-44" aria-label="Filter by status">
            <SelectValue placeholder="All statuses" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL_STATUS}>All statuses</SelectItem>
            <SelectItem value="pending">Pending</SelectItem>
            <SelectItem value="approved">Approved</SelectItem>
            <SelectItem value="rejected">Rejected</SelectItem>
            <SelectItem value="cancelled">Cancelled</SelectItem>
          </SelectContent>
        </Select>

        <Select
          value={filters.leaveTypeId ?? ALL_TYPE}
          onValueChange={(value) =>
            setFilters((current) => ({
              ...current,
              leaveTypeId: value === ALL_TYPE ? undefined : value,
              page: 1,
            }))
          }
        >
          <SelectTrigger className="w-48" aria-label="Filter by leave type">
            <SelectValue placeholder="All leave types" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL_TYPE}>All leave types</SelectItem>
            {(leaveTypes ?? []).map((leaveType) => (
              <SelectItem key={leaveType.id} value={leaveType.id}>
                {leaveType.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <div className="flex items-center gap-2">
          <Input
            type="date"
            value={filters.startDateFrom ?? ""}
            onChange={(event) =>
              setFilters((current) => ({ ...current, startDateFrom: event.target.value || undefined, page: 1 }))
            }
            aria-label="Start date from"
            className="w-40"
          />
          <span className="text-sm text-muted-foreground">to</span>
          <Input
            type="date"
            value={filters.startDateTo ?? ""}
            onChange={(event) =>
              setFilters((current) => ({ ...current, startDateTo: event.target.value || undefined, page: 1 }))
            }
            aria-label="Start date to"
            className="w-40"
          />
        </div>
      </div>

      {requestsQuery.isLoading ? (
        <PageLoader label="Loading leave requests…" />
      ) : requestsQuery.isError ? (
        <ErrorState
          title="Couldn't load leave requests"
          onRetry={() => {
            void requestsQuery.refetch();
          }}
        />
      ) : requestsQuery.data && requestsQuery.data.items.length > 0 ? (
        <div className="rounded-lg border border-border">
          <LeaveHistoryTable requests={requestsQuery.data.items} showEmployeeColumn />
          <Pagination
            page={requestsQuery.data.meta.page}
            totalPages={requestsQuery.data.meta.total_pages}
            totalCount={requestsQuery.data.meta.total_count}
            pageSize={requestsQuery.data.meta.page_size}
            onPageChange={(page) => setFilters((current) => ({ ...current, page }))}
          />
        </div>
      ) : (
        <EmptyState
          title="No leave requests match these filters"
          description="Try widening the date range or clearing a filter."
        />
      )}

      {canManage ? (
        <ApplyLeaveDialog
          open={applyDialogOpen}
          onOpenChange={setApplyDialogOpen}
          leaveTypes={leaveTypes ?? []}
          allowEmployeeSelection
          onSubmit={handleApplySubmit}
          isSubmitting={applyForEmployeeMutation.isPending}
          submitError={applyError}
        />
      ) : null}

      {canManage ? (
        <BalanceAdjustmentDialog
          open={balanceDialog !== null}
          onOpenChange={(open) => !open && setBalanceDialog(null)}
          mode={balanceDialog ?? "adjust"}
          leaveTypes={leaveTypes ?? []}
          onSubmit={handleBalanceSubmit}
          isSubmitting={adjustBalanceMutation.isPending}
          submitError={balanceError}
        />
      ) : null}
    </div>
  );
}
