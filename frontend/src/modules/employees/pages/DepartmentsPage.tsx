import { ArrowLeft, Plus } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Pagination } from "@/components/ui/pagination";
import { EmptyState, ErrorState, PageHeader, PageLoader } from "@/components/common";
import { ROUTE_PATHS } from "@/app/router/routePaths";
import { DepartmentFormDialog } from "@/modules/employees/components/DepartmentFormDialog";
import { DepartmentTable } from "@/modules/employees/components/DepartmentTable";
import {
  useCreateDepartmentMutation,
  useUpdateDepartmentMutation,
} from "@/modules/employees/hooks/useDepartmentMutations";
import { useDepartmentsQuery } from "@/modules/employees/hooks/useDepartmentQueries";
import type { Department, DepartmentListFilters } from "@/modules/employees/types/department.types";
import type { DepartmentFormValues } from "@/modules/employees/validation/departmentSchema";

const DEFAULT_FILTERS: DepartmentListFilters = { page: 1, pageSize: 25 };

/**
 * Department CRUD (Phase 12) — a sub-view of the Employee module, reached
 * only via the Employee List page's header action, never the sidebar (see
 * EmployeeListPage.tsx's docstring). Create/Edit happen in one shared
 * dialog (DepartmentFormDialog) rather than separate pages, matching the
 * small field set EMPLOYEE_API.md documents for this resource.
 */
export function DepartmentsPage() {
  const navigate = useNavigate();
  const [filters, setFilters] = useState<DepartmentListFilters>(DEFAULT_FILTERS);
  const { data, isLoading, isError, refetch } = useDepartmentsQuery(filters);
  const createMutation = useCreateDepartmentMutation();
  const updateMutation = useUpdateDepartmentMutation();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingDepartment, setEditingDepartment] = useState<Department | undefined>(undefined);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const openCreateDialog = () => {
    setEditingDepartment(undefined);
    setSubmitError(null);
    setDialogOpen(true);
  };

  const openEditDialog = (department: Department) => {
    setEditingDepartment(department);
    setSubmitError(null);
    setDialogOpen(true);
  };

  const handleSubmit = (values: DepartmentFormValues) => {
    setSubmitError(null);
    const input = {
      name: values.name,
      code: values.code,
      parentDepartmentId: values.parentDepartmentId ?? null,
      headEmployeeId: values.headEmployeeId ?? null,
    };

    if (editingDepartment) {
      updateMutation.mutate(
        { departmentId: editingDepartment.id, input: { ...input, isActive: values.isActive } },
        {
          onSuccess: (department) => {
            toast.success(`${department.name} was updated.`);
            setDialogOpen(false);
          },
          onError: (error) => setSubmitError(error.message),
        },
      );
    } else {
      createMutation.mutate(input, {
        onSuccess: (department) => {
          toast.success(`${department.name} was created.`);
          setDialogOpen(false);
        },
        onError: (error) => setSubmitError(error.message),
      });
    }
  };

  return (
    <div>
      <PageHeader
        title="Departments"
        description="Departments used across the Employee directory."
        actions={
          <>
            <Button variant="ghost" onClick={() => navigate(ROUTE_PATHS.dashboard.employees)}>
              <ArrowLeft className="size-4" aria-hidden="true" />
              Back to Employees
            </Button>
            <Button onClick={openCreateDialog}>
              <Plus className="size-4" aria-hidden="true" />
              New Department
            </Button>
          </>
        }
      />

      {isLoading ? (
        <PageLoader label="Loading departments…" />
      ) : isError ? (
        <ErrorState
          title="Couldn't load departments"
          onRetry={() => {
            void refetch();
          }}
        />
      ) : data && data.items.length > 0 ? (
        <div className="rounded-lg border border-border">
          <DepartmentTable departments={data.items} onEdit={openEditDialog} />
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
          title="No departments yet"
          description="Create the first department to start assigning employees to it."
          action={
            <Button onClick={openCreateDialog}>
              <Plus className="size-4" aria-hidden="true" />
              New Department
            </Button>
          }
        />
      )}

      <DepartmentFormDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        department={editingDepartment}
        onSubmit={handleSubmit}
        isSubmitting={createMutation.isPending || updateMutation.isPending}
        submitError={submitError}
      />
    </div>
  );
}
