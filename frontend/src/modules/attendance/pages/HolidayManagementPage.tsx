import { ArrowLeft, Plus } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { ROUTE_PATHS } from "@/app/router/routePaths";
import { Button } from "@/components/ui/button";
import { Pagination } from "@/components/ui/pagination";
import { EmptyState, ErrorState, PageHeader, PageLoader } from "@/components/common";
import { useHasPermission } from "@/lib/auth/usePermission";
import { HolidayFormDialog } from "@/modules/attendance/components/HolidayFormDialog";
import { HolidayTable } from "@/modules/attendance/components/HolidayTable";
import {
  useCreateHolidayMutation,
  useUpdateHolidayMutation,
} from "@/modules/attendance/hooks/useHolidayMutations";
import { useHolidaysQuery } from "@/modules/attendance/hooks/useHolidayQueries";
import type { Holiday, HolidayListFilters } from "@/modules/attendance/types/holiday.types";
import type { HolidayFormValues } from "@/modules/attendance/validation/holidaySchema";

const DEFAULT_FILTERS: HolidayListFilters = { page: 1, pageSize: 25, ordering: "holiday_date" };

/**
 * Holiday Management — a sub-view of the Attendance module, reached only via
 * the Attendance home page's header action, mirroring Department
 * Management's relationship to the Employee module (DepartmentsPage.tsx).
 * Used to define upcoming holidays consumed by Leave's working-days
 * calculation; the rest of Attendance (actual clock-in/out) is future work.
 */
export function HolidayManagementPage() {
  const navigate = useNavigate();
  const canManage = useHasPermission("attendance.manage_holidays");
  const [filters, setFilters] = useState<HolidayListFilters>(DEFAULT_FILTERS);
  const { data, isLoading, isError, refetch } = useHolidaysQuery(filters);
  const createMutation = useCreateHolidayMutation();
  const updateMutation = useUpdateHolidayMutation();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingHoliday, setEditingHoliday] = useState<Holiday | undefined>(undefined);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const openCreateDialog = () => {
    setEditingHoliday(undefined);
    setSubmitError(null);
    setDialogOpen(true);
  };

  const openEditDialog = (holiday: Holiday) => {
    setEditingHoliday(holiday);
    setSubmitError(null);
    setDialogOpen(true);
  };

  const handleSubmit = (values: HolidayFormValues) => {
    setSubmitError(null);
    const input = {
      name: values.name,
      holidayDate: values.holidayDate,
      description: values.description ?? "",
    };

    if (editingHoliday) {
      updateMutation.mutate(
        { holidayId: editingHoliday.id, input: { ...input, isActive: values.isActive } },
        {
          onSuccess: (holiday) => {
            toast.success(`${holiday.name} was updated.`);
            setDialogOpen(false);
          },
          onError: (error) => setSubmitError(error.message),
        },
      );
    } else {
      createMutation.mutate(input, {
        onSuccess: (holiday) => {
          toast.success(`${holiday.name} was created.`);
          setDialogOpen(false);
        },
        onError: (error) => setSubmitError(error.message),
      });
    }
  };

  return (
    <div>
      <PageHeader
        title="Holiday Management"
        description="Upcoming holidays used to calculate working days for leave."
        actions={
          <>
            <Button variant="ghost" onClick={() => navigate(ROUTE_PATHS.dashboard.attendance)}>
              <ArrowLeft className="size-4" aria-hidden="true" />
              Back to Attendance
            </Button>
            {canManage ? (
              <Button onClick={openCreateDialog}>
                <Plus className="size-4" aria-hidden="true" />
                New Holiday
              </Button>
            ) : null}
          </>
        }
      />

      {isLoading ? (
        <PageLoader label="Loading holidays…" />
      ) : isError ? (
        <ErrorState
          title="Couldn't load holidays"
          onRetry={() => {
            void refetch();
          }}
        />
      ) : data && data.items.length > 0 ? (
        <div className="rounded-lg border border-border">
          <HolidayTable holidays={data.items} onEdit={openEditDialog} />
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
          title="No holidays yet"
          description="Add the first upcoming holiday."
          action={
            canManage ? (
              <Button onClick={openCreateDialog}>
                <Plus className="size-4" aria-hidden="true" />
                New Holiday
              </Button>
            ) : undefined
          }
        />
      )}

      <HolidayFormDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        holiday={editingHoliday}
        onSubmit={handleSubmit}
        isSubmitting={createMutation.isPending || updateMutation.isPending}
        submitError={submitError}
      />
    </div>
  );
}
