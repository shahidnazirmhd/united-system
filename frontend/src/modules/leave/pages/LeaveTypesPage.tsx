import { ArrowLeft, Plus } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Pagination } from "@/components/ui/pagination";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { EmptyState, ErrorState, PageHeader, PageLoader } from "@/components/common";
import { ROUTE_PATHS } from "@/app/router/routePaths";
import { ApiError } from "@/lib/api/types";
import { useDebouncedValue } from "@/hooks";
import { LeaveTypeFormDialog } from "@/modules/leave/components/LeaveTypeFormDialog";
import { LeaveTypeTable } from "@/modules/leave/components/LeaveTypeTable";
import {
  useCreateLeaveTypeMutation,
  useUpdateLeaveTypeMutation,
} from "@/modules/leave/hooks/useLeaveTypeMutations";
import { useManagedLeaveTypesQuery } from "@/modules/leave/hooks/useLeaveTypeQueries";
import type { LeaveType, LeaveTypeListFilters } from "@/modules/leave/types/leave.types";
import type { LeaveTypeFormValues } from "@/modules/leave/validation/leaveTypeSchema";

const ALL_VALUE = "__all__";
const DEFAULT_FILTERS: LeaveTypeListFilters = { page: 1, pageSize: 25 };

/**
 * Leave Type Management (Phase 13) — a sub-view of the Leave module,
 * reached only via the Leave Dashboard's header action, never its own
 * sidebar entry — same "Departments under Employees"/"Roles under Users"
 * precedent. No delete action: `leave_types` is `RESTRICT`-referenced by
 * every balance/request row, so deactivation via `is_active` is the only
 * removal path (matches Department's own precedent exactly).
 */
export function LeaveTypesPage() {
  const navigate = useNavigate();
  const [filters, setFilters] = useState<LeaveTypeListFilters>(DEFAULT_FILTERS);
  const [searchInput, setSearchInput] = useState("");
  const debouncedSearch = useDebouncedValue(searchInput);

  const effectiveFilters: LeaveTypeListFilters = {
    ...filters,
    search: debouncedSearch || undefined,
  };
  const { data, isLoading, isError, refetch } = useManagedLeaveTypesQuery(effectiveFilters);
  const createMutation = useCreateLeaveTypeMutation();
  const updateMutation = useUpdateLeaveTypeMutation();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingLeaveType, setEditingLeaveType] = useState<LeaveType | undefined>(undefined);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const openCreateDialog = () => {
    setEditingLeaveType(undefined);
    setSubmitError(null);
    setDialogOpen(true);
  };

  const openEditDialog = (leaveType: LeaveType) => {
    setEditingLeaveType(leaveType);
    setSubmitError(null);
    setDialogOpen(true);
  };

  const handleSubmit = (values: LeaveTypeFormValues) => {
    setSubmitError(null);
    const onSettled = {
      onSuccess: (leaveType: LeaveType) => {
        toast.success(`${leaveType.name} was ${editingLeaveType ? "updated" : "created"}.`);
        setDialogOpen(false);
      },
      onError: (error: unknown) => {
        setSubmitError(
          error instanceof ApiError ? error.message : "Could not save this leave type.",
        );
      },
    };

    // "none" is a form-only sentinel (shadcn's `Select` can't use an empty
    // string as a value) — translate to `null` here, the one place this
    // form's values cross into the wire-shaped API input.
    const mapsToEmployeeStatus =
      values.mapsToEmployeeStatus === "none" ? null : values.mapsToEmployeeStatus;

    if (editingLeaveType) {
      updateMutation.mutate(
        {
          leaveTypeId: editingLeaveType.id,
          input: {
            name: values.name,
            code: values.code,
            defaultAnnualDays: values.defaultAnnualDays,
            isPaid: values.isPaid,
            requiresApproval: values.requiresApproval,
            isActive: values.isActive,
            mapsToEmployeeStatus,
          },
        },
        onSettled,
      );
    } else {
      createMutation.mutate(
        {
          name: values.name,
          code: values.code,
          defaultAnnualDays: values.defaultAnnualDays,
          isPaid: values.isPaid,
          requiresApproval: values.requiresApproval,
          mapsToEmployeeStatus,
        },
        onSettled,
      );
    }
  };

  return (
    <div>
      <PageHeader
        title="Leave Types"
        description="Leave types available across the organization."
        actions={
          <>
            <Button variant="ghost" onClick={() => navigate(ROUTE_PATHS.dashboard.leave)}>
              <ArrowLeft className="size-4" aria-hidden="true" />
              Back to Leave
            </Button>
            <Button onClick={openCreateDialog}>
              <Plus className="size-4" aria-hidden="true" />
              New Leave Type
            </Button>
          </>
        }
      />

      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center">
        <Input
          value={searchInput}
          onChange={(event) => setSearchInput(event.target.value)}
          placeholder="Search by name or code…"
          className="sm:w-64"
          aria-label="Search leave types"
        />
        <Select
          value={filters.isActive === undefined ? ALL_VALUE : String(filters.isActive)}
          onValueChange={(value) =>
            setFilters((current) => ({
              ...current,
              isActive: value === ALL_VALUE ? undefined : value === "true",
              page: 1,
            }))
          }
        >
          <SelectTrigger className="sm:w-40" aria-label="Filter by status">
            <SelectValue placeholder="All statuses" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL_VALUE}>All statuses</SelectItem>
            <SelectItem value="true">Active</SelectItem>
            <SelectItem value="false">Inactive</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {isLoading ? (
        <PageLoader label="Loading leave types…" />
      ) : isError ? (
        <ErrorState
          title="Couldn't load leave types"
          onRetry={() => {
            void refetch();
          }}
        />
      ) : data && data.items.length > 0 ? (
        <div className="rounded-lg border border-border">
          <LeaveTypeTable leaveTypes={data.items} onEdit={openEditDialog} />
          <Pagination
            page={data.meta.page}
            totalPages={data.meta.total_pages}
            totalCount={data.meta.total_count}
            pageSize={data.meta.page_size}
            onPageChange={(page) => setFilters((current) => ({ ...current, page }))}
          />
        </div>
      ) : (
        <EmptyState
          title="No leave types yet"
          description="Create the first leave type to start assigning employee entitlements."
          action={
            <Button onClick={openCreateDialog}>
              <Plus className="size-4" aria-hidden="true" />
              New Leave Type
            </Button>
          }
        />
      )}

      <LeaveTypeFormDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        leaveType={editingLeaveType}
        onSubmit={handleSubmit}
        isSubmitting={createMutation.isPending || updateMutation.isPending}
        submitError={submitError}
      />
    </div>
  );
}
