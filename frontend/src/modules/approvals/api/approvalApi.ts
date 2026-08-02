import { API_ENDPOINTS } from "@/lib/api/endpoints";
import { httpClient } from "@/lib/api/httpClient";
import type { ApiSuccessResponse } from "@/lib/api/types";
import type { ApprovalRequest, ApprovalStep, DecideApprovalInput } from "@/modules/approvals/types/approval.types";

/** The exact wire shape APPROVALS_API.md documents for `ApprovalRequestResponseSerializer`. */
interface ApprovalStepWireResponse {
  id: string;
  approval_request_id: string;
  level: number;
  // Exactly one of these two is ever non-null (Phase 13 — a level can now
  // be assigned to one specific employee OR to anyone holding a
  // permission code, see APPROVALS_API.md).
  approver_employee_id: string | null;
  approver_permission_code: string | null;
  // Approval Workflow Changes review round — see APPROVALS_API.md's
  // "Notifying the requester..." section and the Error codes table's
  // `approval_channel_not_allowed` entry. `null` means "either channel, no
  // restriction" (every step before this review round).
  restricted_to_channel: string | null;
  // Approval Workflow Changes v2 — see APPROVALS_API.md's "Restricting a
  // step to one channel" section's dual-mode note.
  permission_required_for_channel: string | null;
  // Approval Workflow Changes v2 — who actually decided this step.
  decided_by_employee_id: string | null;
  // Enrichment, populated for `decided_by_employee_id` once decided, else
  // `approver_employee_id` while pending; never for a still-pending,
  // non-dual-mode permission-based step, which has no single employee to
  // name yet.
  approver_employee_name: string | null;
  approver_employee_code: string | null;
  status: string;
  comments: string | null;
  decided_at: string | null;
}

interface ApprovalRequestWireResponse {
  id: string;
  subject_type: string;
  subject_id: string;
  requested_by_employee_id: string;
  subject_summary: string;
  status: string;
  current_level: number;
  steps: ApprovalStepWireResponse[];
}

function toStep(wire: ApprovalStepWireResponse): ApprovalStep {
  return {
    id: wire.id,
    approvalRequestId: wire.approval_request_id,
    level: wire.level,
    approverEmployeeId: wire.approver_employee_id,
    approverPermissionCode: wire.approver_permission_code,
    restrictedToChannel: wire.restricted_to_channel,
    permissionRequiredForChannel: wire.permission_required_for_channel,
    decidedByEmployeeId: wire.decided_by_employee_id,
    approverEmployeeName: wire.approver_employee_name,
    approverEmployeeCode: wire.approver_employee_code,
    status: wire.status as ApprovalStep["status"],
    comments: wire.comments,
    decidedAt: wire.decided_at,
  };
}

function toApprovalRequest(wire: ApprovalRequestWireResponse): ApprovalRequest {
  return {
    id: wire.id,
    subjectType: wire.subject_type,
    subjectId: wire.subject_id,
    requestedByEmployeeId: wire.requested_by_employee_id,
    subjectSummary: wire.subject_summary,
    status: wire.status as ApprovalRequest["status"],
    currentLevel: wire.current_level,
    steps: wire.steps.map(toStep),
  };
}

/** `GET /api/v1/approvals/pending/me/` */
export async function listMyPendingApprovals(): Promise<ApprovalRequest[]> {
  const response = await httpClient.get<ApiSuccessResponse<ApprovalRequestWireResponse[]>>(
    `${API_ENDPOINTS.approvals}/pending/me/`,
  );
  return response.data.data.map(toApprovalRequest);
}

/** `GET /api/v1/approvals/<id>/` */
export async function getApprovalRequestById(approvalRequestId: string): Promise<ApprovalRequest> {
  const response = await httpClient.get<ApiSuccessResponse<ApprovalRequestWireResponse>>(
    `${API_ENDPOINTS.approvals}/${approvalRequestId}/`,
  );
  return toApprovalRequest(response.data.data);
}

/** `GET /api/v1/approvals/subject/<subject_type>/<subject_id>/` — Phase 13,
 * backs Leave's "View Leave Details" approval-history panel. Empty array
 * (not a 404) both when the subject has no approval history yet and when
 * the caller isn't entitled to see it — see the endpoint's own docstring. */
export async function listApprovalHistoryForSubject(
  subjectType: string,
  subjectId: string,
): Promise<ApprovalRequest[]> {
  const response = await httpClient.get<ApiSuccessResponse<ApprovalRequestWireResponse[]>>(
    `${API_ENDPOINTS.approvals}/subject/${subjectType}/${subjectId}/`,
  );
  return response.data.data.map(toApprovalRequest);
}

/** `POST /api/v1/approvals/<id>/decide/` */
export async function decideApprovalRequest(
  approvalRequestId: string,
  input: DecideApprovalInput,
): Promise<ApprovalRequest> {
  const response = await httpClient.post<ApiSuccessResponse<ApprovalRequestWireResponse>>(
    `${API_ENDPOINTS.approvals}/${approvalRequestId}/decide/`,
    { decision: input.decision, comments: input.comments ?? null },
  );
  return toApprovalRequest(response.data.data);
}
