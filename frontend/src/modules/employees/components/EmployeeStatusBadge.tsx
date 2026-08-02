import { Badge, type BadgeProps } from "@/components/ui/badge";
import type { EmployeeStatus } from "@/modules/employees/types/employee.types";

const VARIANT_BY_STATUS: Record<EmployeeStatus, NonNullable<BadgeProps["variant"]>> = {
  active: "success",
  on_leave: "warning",
  suspended: "warning",
  terminated: "destructive",
};

const LABEL_BY_STATUS: Record<EmployeeStatus, string> = {
  active: "Active",
  on_leave: "On Leave",
  suspended: "Suspended",
  terminated: "Terminated",
};

export function EmployeeStatusBadge({ status }: { status: EmployeeStatus }) {
  return <Badge variant={VARIANT_BY_STATUS[status]}>{LABEL_BY_STATUS[status]}</Badge>;
}
