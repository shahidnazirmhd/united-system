import { Building2, Lock, Plus, Users as UsersIcon } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Pagination } from "@/components/ui/pagination";
import { EmptyState, ErrorState, PageHeader, PageLoader } from "@/components/common";
import { ROUTE_PATHS } from "@/app/router/routePaths";
import { useHasPermission } from "@/lib/auth";
import { EmployeeFiltersBar } from "@/modules/employees/components/EmployeeFiltersBar";
import { EmployeeTable } from "@/modules/employees/components/EmployeeTable";
import {
  useActivateEmployeeMutation,
  useDeactivateEmployeeMutation,
} from "@/modules/employees/hooks/useEmployeeMutations";
import { useEmployeesQuery } from "@/modules/employees/hooks/useEmployeeQueries";
import type { Employee, EmployeeListFilters } from "@/modules/employees/types/employee.types";

const DEFAULT_FILTERS: EmployeeListFilters = { page: 1, pageSize: 25 };

/**
 * Employee List (Phase 12): search/filter/pagination over
 * `GET /api/v1/employees/`. Departments is deliberately reachable only from
 * this page's header action, not the sidebar — it's a sub-view of the
 * Employee bounded context (see EMPLOYEE_API.md's Department CRUD section),
 * not its own top-level module.
 *
 * RBAC review round: gated on `employees.view_employees`/
 * `employees.manage_employees`, same restricted-`EmptyState` pattern as
 * `UserListPage.tsx`/`RolesPage.tsx`/`LeaveDashboardPage.tsx`. New Employee/
 * Edit/Activate/Deactivate further require `employees.manage_employees`
 * specifically.
 */
export function EmployeeListPage() {
  const navigate = useNavigate();
  const canManage = useHasPermission("employees.manage_employees");
  const canViewOnly = useHasPermission("employees.view_employees");
  const canView = canManage || canViewOnly;
  const [filters, setFilters] = useState<EmployeeListFilters>(DEFAULT_FILTERS);
  const { data, isLoading, isError, refetch } = useEmployeesQuery(filters);
  const activateMutation = useActivateEmployeeMutation();
  const deactivateMutation = useDeactivateEmployeeMutation();

  if (!canView) {
    return (
      <div>
        <PageHeader
          title="Employees"
          description="Directory, profiles, and employment status for every employee."
        />
        <EmptyState
          icon={Lock}
          title="You don't have access to Employee Management"
          description="Ask an administrator for the employees.view_employees permission if you believe this is a mistake."
        />
      </div>
    );
  }

  const handleActivate = (employee: Employee) => {
    activateMutation.mutate(employee.id, {
      onSuccess: () => toast.success(`${employee.fullName} activated.`),
      onError: (error) => toast.error(error.message),
    });
  };

  const handleDeactivate = (employee: Employee) => {
    deactivateMutation.mutate(employee.id, {
      onSuccess: () => toast.success(`${employee.fullName} deactivated.`),
      onError: (error) => toast.error(error.message),
    });
  };

  return (
    <div>
      <PageHeader
        title="Employees"
        description="Directory, profiles, and employment status for every employee."
        actions={
          <>
            <Button variant="outline" onClick={() => navigate(ROUTE_PATHS.dashboard.employeeDepartments)}>
              <Building2 className="size-4" aria-hidden="true" />
              Departments
            </Button>
            {canManage ? (
              <Button onClick={() => navigate(ROUTE_PATHS.dashboard.employeesNew)}>
                <Plus className="size-4" aria-hidden="true" />
                New Employee
              </Button>
            ) : null}
          </>
        }
      />

      <div className="space-y-4">
        <EmployeeFiltersBar filters={filters} onFiltersChange={setFilters} />

        {isLoading ? (
          <PageLoader label="Loading employees…" />
        ) : isError ? (
          <ErrorState
            title="Couldn't load employees"
            onRetry={() => {
              void refetch();
            }}
          />
        ) : data && data.items.length > 0 ? (
          <div className="rounded-lg border border-border">
            <EmployeeTable
              employees={data.items}
              canManage={canManage}
              onActivate={handleActivate}
              onDeactivate={handleDeactivate}
            />
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
            icon={UsersIcon}
            title="No employees found"
            description={
              canManage
                ? "Try adjusting your filters, or create the first employee record."
                : "Try adjusting your filters."
            }
            action={
              canManage ? (
                <Button onClick={() => navigate(ROUTE_PATHS.dashboard.employeesNew)}>
                  <Plus className="size-4" aria-hidden="true" />
                  New Employee
                </Button>
              ) : undefined
            }
          />
        )}
      </div>
    </div>
  );
}
