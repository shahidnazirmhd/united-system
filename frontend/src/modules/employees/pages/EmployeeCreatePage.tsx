import { Lock } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { EmptyState, PageHeader } from "@/components/common";
import { buildEmployeeDetailPath, ROUTE_PATHS } from "@/app/router/routePaths";
import { useHasPermission } from "@/lib/auth";
import { EmployeeForm } from "@/modules/employees/components/EmployeeForm";
import { useCreateEmployeeMutation } from "@/modules/employees/hooks/useEmployeeMutations";
import type { EmployeeFormValues } from "@/modules/employees/validation/employeeSchema";

/**
 * Create Employee (Phase 12): `POST /api/v1/employees/`.
 *
 * RBAC review round: this route is reachable directly by URL even though
 * `EmployeeListPage.tsx` now only ever links here for `employees.manage_employees`
 * holders — this page-level guard closes that gap for a caller who
 * navigates straight to `/employees/new`.
 */
export function EmployeeCreatePage() {
  const navigate = useNavigate();
  const canManage = useHasPermission("employees.manage_employees");
  const mutation = useCreateEmployeeMutation();
  const [submitError, setSubmitError] = useState<string | null>(null);

  if (!canManage) {
    return (
      <div>
        <PageHeader title="New Employee" description="Creates a new employee record." />
        <EmptyState
          icon={Lock}
          title="You don't have access to create employees"
          description="Ask an administrator for the employees.manage_employees permission if you believe this is a mistake."
        />
      </div>
    );
  }

  const handleSubmit = (values: EmployeeFormValues) => {
    setSubmitError(null);
    mutation.mutate(
      {
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
        userId: null,
      },
      {
        onSuccess: (employee) => {
          toast.success(`${employee.fullName} was created.`);
          navigate(buildEmployeeDetailPath(employee.id));
        },
        onError: (error) => setSubmitError(error.message),
      },
    );
  };

  return (
    <div>
      <PageHeader
        title="New Employee"
        description="Creates a new employee record."
        actions={
          <Button variant="ghost" onClick={() => navigate(ROUTE_PATHS.dashboard.employees)}>
            Cancel
          </Button>
        }
      />
      <EmployeeForm
        mode="create"
        onSubmit={handleSubmit}
        isSubmitting={mutation.isPending}
        submitError={submitError}
      />
    </div>
  );
}
