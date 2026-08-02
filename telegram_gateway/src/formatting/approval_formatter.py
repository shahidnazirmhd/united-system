"""Translates the generic Approval Engine's shapes into Telegram message
text — the Approvals-module counterpart to `formatting/leave_formatter.py`.
Pure functions, no I/O.

This file (and `handlers/approval_handlers.py`) is deliberately the ONLY
place in this whole system that turns an approval request's opaque
`subject_summary` string into something a manager reads — the backend
Approval Engine itself never knows this text ends up in Telegram (see
`apps.approvals.application.ports.ApprovalNotificationPort`'s docstring on
the Django side); this Gateway is what actually presents it.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from src.formatting.common import field_or_placeholder

if TYPE_CHECKING:
    from src.api_client.endpoints.approvals import ApprovalRequest

_STATUS_LABELS = {
    "pending": "🟡 Pending",
    "approved": "🟢 Approved",
    "rejected": "🔴 Rejected",
}


def _status_label(status: str) -> str:
    return _STATUS_LABELS.get(status, status.replace("_", " ").title())


def format_no_pending_approvals() -> str:
    return "You have no pending approvals right now."


def format_pending_approval_item(request: ApprovalRequest) -> str:
    """One self-contained message per pending approval — used both by
    `/pending_approvals` (one item per message, each with its own
    Approve/Reject buttons) and, in spirit, by a fresh push notification;
    kept as free text (not truncated to a button label) so the full summary
    is always fully readable, unlike `leave_formatter`'s button-label
    variants."""
    return f"📋 *Approval Requested* (level {request.current_level})\n\n{request.subject_summary}"


def format_approval_requested_push(*, subject_summary: str, level: int) -> str:
    """The unsolicited push notification sent the moment a new level opens
    — same content shape as `format_pending_approval_item`, kept as its own
    function since the caller (an `/internal/notify` payload) has only the
    opaque fields, not a parsed `ApprovalRequest`."""
    return f"📋 *Approval Requested* (level {level})\n\n{subject_summary}\n\nPlease Approve or Reject below."


def format_approval_decided_push(*, subject_summary: str, final_status: str, comments: str | None) -> str:
    """The push notification sent to the original requester once their
    request reaches a final decision."""
    lines = [f"{_status_label(final_status)} — your request has been decided.", "", subject_summary]
    if comments:
        lines.append(f"\n💬 Comments: {field_or_placeholder(comments)}")
    return "\n".join(lines)


def format_approval_step_advanced_push(*, message: str, subject_summary: str) -> str:
    """Leave review round: the push sent to the original requester when a
    NON-final level is approved and the chain moves on (e.g. "manager
    approved, now awaiting HR") — distinct from `format_approval_decided_push`
    above, which only ever fires once the whole chain concludes. `message`
    is the complete, already-composed sentence the backend forwarded
    (`ApproverAssignment.requester_notification_message` on the Django
    side); this function only wraps it in the same light presentation
    chrome (an icon, the subject line) every other push here uses — it
    does not invent any wording of its own, since the backend's subject
    module (Leave) already fully composed the message."""
    return f"🔔 {message}\n\n{subject_summary}"


def format_approval_comment_prompt(decision: str) -> str:
    verb = "approval" if decision == "approve" else "rejection"
    return f'Want to add a comment with your {verb}? Send it, or reply "skip".'


def format_approval_decision_result(request: ApprovalRequest) -> str:
    if request.status == "pending":
        # Approved at a non-final level — the chain advanced to a new
        # level rather than concluding (see
        # apps.approvals.application.services.approval_service's
        # dynamic-levels mechanism). This is now a live path: Leave's chain
        # is two levels (manager, then any leave.manage_leave holder), so a
        # manager's Telegram approval always lands here, not on the
        # final-decision branch below — see LEAVE_API.md's "Approval
        # integration" section.
        return f"✅ Approved. This request has moved to level {request.current_level} for further approval."
    return f"{_status_label(request.status)} Decision recorded."
