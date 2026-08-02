/**
 * Public surface of the approvals module — same convention as
 * `modules/employees`/`modules/users`, extended slightly: this module also
 * exports `ApprovalHistoryPanel` and `SUBJECT_TYPE_LEAVE_REQUEST` (not just
 * its page), because — like the backend's own generic, subject-agnostic
 * Approval Engine — a subject module (Leave today, any future one) needs a
 * sanctioned way to embed this module's approval-history UI in its own
 * detail page without duplicating the fetch/render logic. Leave depends on
 * this module's public surface; this module never imports Leave's — same
 * one-way dependency direction APPROVALS_API.md documents for the backend.
 */
export { ApprovalHistoryPanel } from "@/modules/approvals/components/ApprovalHistoryPanel";
export { ApprovalsPage } from "@/modules/approvals/pages/ApprovalsPage";
export { SUBJECT_TYPE_LEAVE_REQUEST } from "@/modules/approvals/types/approval.types";
