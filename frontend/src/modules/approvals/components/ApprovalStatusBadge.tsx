import { Badge, type BadgeProps } from "@/components/ui/badge";
import type { ApprovalStatus } from "@/modules/approvals/types/approval.types";

const VARIANT_BY_STATUS: Record<ApprovalStatus, NonNullable<BadgeProps["variant"]>> = {
  pending: "warning",
  approved: "success",
  rejected: "destructive",
  // Round 17 item 2 — the subject (e.g. the leave request) was cancelled,
  // closing this approval request; distinct from "rejected", so a distinct
  // (neutral, not alarming) badge color.
  cancelled: "secondary",
};

const LABEL_BY_STATUS: Record<ApprovalStatus, string> = {
  pending: "Pending",
  approved: "Approved",
  rejected: "Rejected",
  cancelled: "Cancelled",
};

export function ApprovalStatusBadge({ status }: { status: ApprovalStatus }) {
  return <Badge variant={VARIANT_BY_STATUS[status]}>{LABEL_BY_STATUS[status]}</Badge>;
}
