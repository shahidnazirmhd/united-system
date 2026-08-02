import { Lock } from "lucide-react";
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { EmptyState, ErrorState, PageHeader, PageLoader } from "@/components/common";
import { buildEmployeeDetailPath } from "@/app/router/routePaths";
import { useHasPermission } from "@/lib/auth";
import { EmployeeForm } from "@/modules/employees/components/EmployeeForm";
import { useUpdateEmployeeMutation } from "@/modules/employees/hooks/useEmployeeMutations";
import { useEmployeeQuery } from "@/modules/employees/hooks/useEmployeeQueries";
import type { EmployeeFormValues } from "@/modules/employees/validation/employeeSchema";

/**
 * Edit Employee (Phase 12): `PATCH /api/v1/employees/{id}/`. Full-replace
 * update, matching EMPLOYEE_API.md — every field is re-submitted, not just
 * the ones that changed.
 *
 * RBAC review round: page-level guard for a caller who navigates straight
 * to `/employees/{id}/edit` without `employees.manage_employees` — same
 * reasoning as `EmployeeCreatePage.tsx`'s own guard.
 */
export function EmployeeEditPage() {
  const { employeeId } = useParams<{ employeeId: string }>();
  const navigate = useNavigate();
  const canManage = useHasPermission("employees.manage_employees");
  const { data: employee, isLoading, isError, refetch } = useEmployeeQuery(employeeId);
  const mutation = useUpdateEmployeeMutation();
  const [submitError, setSubmitError] = useState<string | null>(null);

  if (!canManage) {
    return (
      <div>
        <PageHeader title="Edit Employee" description="" />
        <EmptyState
          icon={Lock}
          title="You don't have access to edit employees"
          description="Ask an administrator for the employees.manage_employees permission if you believe this is a mistake."
        />
      </div>
    );
  }

  if (isLoading) {
    return <PageLoader label="Loading employee…" />;
  }
  if (isError || !employee) {
    return (
      <ErrorState
        title="Couldn't load this employee"
        onRetry={() => {
          void refetch();
        }}
      />
    );
  }

  const handleSubmit = (values: EmployeeFormValues) => {
    setSubmitError(null);
    mutation.mutate(
      {
        employeeId: employee.id,
        input: {
          firstName: values.firstName,
          lastName: values.lastName,
          dateOfBirth: values.dateOfBirth ?? null,
          gender: values.gender ?? null,
          workEmail: values.workEmail,
          personalEmail: values.personalEmail ?? null,
          phoneNumber: values.phoneNumber ?? null,
          departmentId: values.departmentId,
          managerId: values.managerId ?? null,
          jobTitle: values.jobTitle,
          employmentType: values.employmentType,
          dateOfJoining: values.dateOfJoining,
          lastWorkingDate: values.lastWorkingDate ?? null,
        },
      },
      {
        onSuccess: (updated) => {
          toast.success(`${updated.fullName} was updated.`);
          navigate(buildEmployeeDetailPath(updated.id));
        },
        onError: (error) => setSubmitError(error.message),
      },
    );
  };

  return (
    <div>
      <PageHeader
        title={`Edit ${employee.fullName}`}
        description={employee.employeeCode}
        actions={
          <Button variant="ghost" onClick={() => navigate(buildEmployeeDetailPath(employee.id))}>
            Cancel
          </Button>
        }
      />
      <EmployeeForm
        mode="edit"
        employeeIdToExclude={employee.id}
        initialManagerName={employee.managerName}
        defaultValues={{
          firstName: employee.firstName,
          lastName: employee.lastName,
          dateOfBirth: employee.dateOfBirth ?? "",
          gender: employee.gender ?? "",
          workEmail: employee.workEmail,
          personalEmail: employee.personalEmail ?? "",
          phoneNumber: employee.phoneNumber ?? "",
          departmentId: employee.departmentId,
          managerId: employee.managerId ?? "",
          jobTitle: employee.jobTitle,
          employmentType: employee.employmentType,
          dateOfJoining: employee.dateOfJoining,
          lastWorkingDate: employee.lastWorkingDate ?? "",
        }}
        onSubmit={handleSubmit}
        isSubmitting={mutation.isPending}
        submitError={submitError}
      />
    </div>
  );
}
