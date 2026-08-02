/**
 * This module's own domain types — field names/shape mirror
 * APPROVALS_API.md's `ApprovalRequestResponseSerializer`/
 * `ApprovalStepResponseSerializer` exactly, camelCased. Never imported by
 * the foundation or by a peer subject module's internals — Leave's own
 * Leave Request Detail page imports this module's public barrel
 * (`@/modules/approvals`) to show approval history, the same "depend on
 * the generic engine's public surface, never the reverse" direction the
 * backend already enforces (see APPROVALS_API.md's "generic,
 * subject-agnostic engine" framing).
 */
// Round 17 item 2 — "cancelled" is set by the subject module (e.g. Leave)
// closing a still-open approval request because the underlying subject
// itself was cancelled, distinct from "rejected" (an approver's own
// decision) — see the backend's `ApprovalStatus`/`ApprovalStepStatus`
// enums for the full reasoning.
export type ApprovalStatus = "pending" | "approved" | "rejected" | "cancelled";
export type ApprovalStepStatus = "pending" | "approved" | "rejected" | "cancelled";
export type ApprovalDecision = "approve" | "reject";

export interface ApprovalStep {
  id: string;
  approvalRequestId: string;
  level: number;
  // Exactly one of these two is ever non-null — a level assigned to one
  // specific employee, or to anyone currently holding a permission code
  // (Phase 13 — e.g. Leave's HR/Admin review level, "leave.manage_leave").
  approverEmployeeId: string | null;
  approverPermissionCode: string | null;
  // Approval Workflow Changes review round: which channel this step may be
  // decided from — "web" | "telegram" | null (null = either, no
  // restriction; every step before this review round). See
  // `APPROVAL_CHANNEL_TELEGRAM` below and `ApprovalHistoryPanel`'s
  // `isDecidableByCurrentUser` for how the web app uses this to hide a
  // "Decide" action it could never actually submit successfully.
  restrictedToChannel: string | null;
  // Approval Workflow Changes v2 — only meaningful when BOTH
  // `approverEmployeeId` and `approverPermissionCode` are set (a "dual-mode"
  // step, e.g. Leave's level 1: the manager via Telegram, any
  // `approvals.level1_approve` holder via the web). Names the one channel
  // on which `approverPermissionCode` governs instead of
  // `approverEmployeeId` — see `ApprovalHistoryPanel`'s
  // `isDecidableByCurrentUser` for the exact per-channel rule this drives.
  permissionRequiredForChannel: string | null;
  // Approval Workflow Changes v2 — who actually decided this step, distinct
  // from `approverEmployeeId` (who was originally assigned/referenced).
  // `null` until decided. Not directly rendered by this module — the
  // resolved name/code below already reflects whichever party is relevant.
  decidedByEmployeeId: string | null;
  // Enrichment — populated for `decidedByEmployeeId` once decided, else
  // `approverEmployeeId` while still pending; `null` for a still-pending,
  // non-dual-mode permission-based step, which has no single employee to
  // name yet. Lets the HR system show "Pending — Jane Doe (EMP-0042)" /
  // "Approved by ..." without this module needing to know it's "a
  // manager."
  approverEmployeeName: string | null;
  approverEmployeeCode: string | null;
  status: ApprovalStepStatus;
  comments: string | null;
  decidedAt: string | null;
}

export interface ApprovalRequest {
  id: string;
  subjectType: string;
  subjectId: string;
  requestedByEmployeeId: string;
  subjectSummary: string;
  status: ApprovalStatus;
  currentLevel: number;
  steps: ApprovalStep[];
}

export interface DecideApprovalInput {
  decision: ApprovalDecision;
  comments?: string | null;
}

/** Subject-type constants — kept here (not hardcoded at each call site)
 * since a future subject module (Attendance, Overtime, ...) will add its
 * own alongside this one, matching the backend's own per-module
 * `SUBJECT_TYPE_*` constant precedent (see
 * `apps.leave.infrastructure.leave_approval_chain_resolver`). */
export const SUBJECT_TYPE_LEAVE_REQUEST = "leave.leave_request";

/** Approval Workflow Changes review round — mirrors the backend's
 * `apps.approvals.domain.enums.ApprovalChannel.TELEGRAM` value exactly.
 * Used to hide "Decide" for a step restricted entirely to Telegram. */
export const APPROVAL_CHANNEL_TELEGRAM = "telegram";

/** Approval Workflow Changes v2 — mirrors
 * `apps.approvals.domain.enums.ApprovalChannel.WEB` exactly. Needed now
 * that a dual-mode step's `permissionRequiredForChannel` must be compared
 * against "web" specifically (this app IS the web channel) to know
 * whether `approverPermissionCode` or `approverEmployeeId` governs. */
export const APPROVAL_CHANNEL_WEB = "web";
