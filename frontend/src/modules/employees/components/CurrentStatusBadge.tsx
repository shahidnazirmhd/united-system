import { Badge, type BadgeProps } from "@/components/ui/badge";
import {
  CURRENT_STATUS_LABELS,
  type EmployeeCurrentStatus,
} from "@/modules/employees/types/employee.types";

const VARIANT_BY_STATUS: Record<EmployeeCurrentStatus, NonNullable<BadgeProps["variant"]>> = {
  not_joined: "secondary",
  working: "success",
  sick_leave: "warning",
  annual_leave: "warning",
  terminated: "destructive",
  resigned: "destructive",
};

export function CurrentStatusBadge({ status }: { status: EmployeeCurrentStatus }) {
  return <Badge variant={VARIANT_BY_STATUS[status]}>{CURRENT_STATUS_LABELS[status]}</Badge>;
}
