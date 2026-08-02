import { Badge, type BadgeProps } from "@/components/ui/badge";
import type { LeaveRequestStatus } from "@/modules/leave/types/leave.types";

const VARIANT_BY_STATUS: Record<LeaveRequestStatus, NonNullable<BadgeProps["variant"]>> = {
  draft: "secondary",
  pending: "warning",
  approved: "success",
  rejected: "destructive",
  cancelled: "secondary",
};

const LABEL_BY_STATUS: Record<LeaveRequestStatus, string> = {
  draft: "Draft",
  pending: "Pending",
  approved: "Approved",
  rejected: "Rejected",
  cancelled: "Cancelled",
};

export function LeaveStatusBadge({ status }: { status: LeaveRequestStatus }) {
  return <Badge variant={VARIANT_BY_STATUS[status]}>{LABEL_BY_STATUS[status]}</Badge>;
}
