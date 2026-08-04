import { Pencil } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { ErrorState, PageHeader, PageLoader } from "@/components/common";
import { buildEmployeeEditPath } from "@/app/router/routePaths";
import { useCurrentUserQuery } from "@/lib/auth";
import { CurrentStatusControl } from "@/modules/employees/components/CurrentStatusControl";
import { EmployeeLeaveSection } from "@/modules/employees/components/EmployeeLeaveSection";
import { EmployeeStatusBadge } from "@/modules/employees/components/EmployeeStatusBadge";
import {
  useActivateEmployeeMutation,
  useDeactivateEmployeeMutation,
} from "@/modules/employees/hooks/useEmployeeMutations";
import { useEmployeeQuery } from "@/modules/employees/hooks/useEmployeeQueries";

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="space-y-1">
      <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</dt>
      <dd className="text-sm text-foreground">{value || "—"}</dd>
    </div>
  );
}

/** Employee Details (Phase 12): `GET /api/v1/employees/{id}/`. */
export function EmployeeDetailPage() {
  const { employeeId } = useParams<{ employeeId: string }>();
  const navigate = useNavigate();
  const { data: employee, isLoading, isError, refetch } = useEmployeeQuery(employeeId);
  const { data: currentUser } = useCurrentUserQuery();
  const activateMutation = useActivateEmployeeMutation();
  const deactivateMutation = useDeactivateEmployeeMutation();
  const canViewLeave = Boolean(
    currentUser?.permissionCodes.includes("leave.view_leave") ||
    currentUser?.permissionCodes.includes("leave.manage_leave"),
  );
  // RBAC review round: Edit/Activate/Deactivate require employees.manage_employees.
  const canManageEmployees = Boolean(
    currentUser?.permissionCodes.includes("employees.manage_employees"),
  );

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

  const handleActivate = () => {
    activateMutation.mutate(employee.id, {
      onSuccess: () => toast.success(`${employee.fullName} activated.`),
      onError: (error) => toast.error(error.message),
    });
  };

  const handleDeactivate = () => {
    deactivateMutation.mutate(employee.id, {
      onSuccess: () => toast.success(`${employee.fullName} deactivated.`),
      onError: (error) => toast.error(error.message),
    });
  };

  return (
    <div>
      <PageHeader
        title={employee.fullName}
        description={`${employee.employeeCode} · ${employee.jobTitle}`}
        actions={
          canManageEmployees ? (
            <>
              {employee.status === "terminated" ? null : employee.status === "active" ? (
                <Button
                  variant="outline"
                  onClick={handleDeactivate}
                  disabled={deactivateMutation.isPending}
                >
                  Deactivate
                </Button>
              ) : (
                <Button
                  variant="outline"
                  onClick={handleActivate}
                  disabled={activateMutation.isPending}
                >
                  Activate
                </Button>
              )}
              <Button onClick={() => navigate(buildEmployeeEditPath(employee.id))}>
                <Pencil className="size-4" aria-hidden="true" />
                Edit
              </Button>
            </>
          ) : undefined
        }
      />

      <Card>
        <CardContent className="space-y-6 pt-6">
          <div className="flex flex-wrap items-center gap-3">
            <EmployeeStatusBadge status={employee.status} />
            <Badge variant={employee.userId ? "success" : "secondary"}>
              User account linked: {employee.userId ? "Yes" : "No"}
            </Badge>
            {employee.userId ? (
              <span className="text-xs text-muted-foreground">
                {employee.linkedUserEmail ?? "Linked (email unavailable)"}
              </span>
            ) : null}
          </div>

          <div className="flex items-center gap-3">
            <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Current status
            </span>
            <CurrentStatusControl employee={employee} canManage={canManageEmployees} />
          </div>

          <Separator />

          <dl className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            <Field label="Work email" value={employee.workEmail} />
            <Field label="Personal email" value={employee.personalEmail ?? ""} />
            <Field label="Phone number" value={employee.phoneNumber ?? ""} />
            <Field label="Department" value={employee.departmentName ?? ""} />
            <Field
              label="Manager"
              value={
                // Round 16 item 4 — a top-level employee (e.g. CEO/MD) is
                // assigned as their own manager, so leave approval routes
                // to themselves. Labelled explicitly here rather than
                // showing their own name back at them unexplained.
                employee.managerId === employee.id
                  ? "Self (top-level — approves own leave)"
                  : (employee.managerName ?? "")
              }
            />
            <Field label="Employment type" value={employee.employmentType.replace("_", " ")} />
            <Field label="Date of joining" value={employee.dateOfJoining} />
            <Field label="Date of birth" value={employee.dateOfBirth ?? ""} />
            <Field label="Gender" value={employee.gender ?? ""} />
            <Field label="Last working date" value={employee.lastWorkingDate ?? ""} />
            <Field
              label="Telegram"
              value={
                employee.isLinkedToTelegram
                  ? `Linked (${employee.telegramUsername ?? ""})`
                  : "Not linked"
              }
            />
          </dl>
        </CardContent>
      </Card>

      {canViewLeave ? (
        <div className="mt-6">
          <h2 className="mb-3 text-xl font-semibold text-foreground">Leave</h2>
          <EmployeeLeaveSection employeeId={employee.id} />
        </div>
      ) : null}
    </div>
  );
}
