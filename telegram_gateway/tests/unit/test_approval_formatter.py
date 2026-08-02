"""Unit tests for formatting/approval_formatter.py — pure functions, no I/O."""
from __future__ import annotations

from src.api_client.endpoints.approvals import ApprovalRequest, ApprovalStep
from src.formatting.approval_formatter import (
    format_approval_comment_prompt,
    format_approval_decided_push,
    format_approval_decision_result,
    format_approval_requested_push,
    format_approval_step_advanced_push,
    format_no_pending_approvals,
    format_pending_approval_item,
)

_PENDING_STEP = ApprovalStep(
    id="step-1", approval_request_id="req-1", level=1, approver_employee_id="mgr-1", status="pending",
    comments=None, decided_at=None,
)

_PENDING_REQUEST = ApprovalRequest(
    id="req-1", subject_type="leave.leave_request", subject_id="leave-req-1", requested_by_employee_id="emp-1",
    subject_summary="Annual Leave: 2026-09-01 -> 2026-09-03 (3 days)", status="pending", current_level=1,
    steps=[_PENDING_STEP],
)


def test_format_no_pending_approvals():
    assert "no pending approvals" in format_no_pending_approvals().lower()


def test_format_pending_approval_item_includes_summary_and_level():
    text = format_pending_approval_item(_PENDING_REQUEST)

    assert "Annual Leave" in text
    assert "level 1" in text


def test_format_approval_requested_push_includes_summary_and_level():
    text = format_approval_requested_push(subject_summary="Annual Leave: 3 days", level=2)

    assert "Annual Leave: 3 days" in text
    assert "level 2" in text
    assert "Approve or Reject" in text


def test_format_approval_decided_push_approved_includes_comments():
    text = format_approval_decided_push(
        subject_summary="Annual Leave: 3 days", final_status="approved", comments="Enjoy!"
    )

    assert "Approved" in text
    assert "Annual Leave: 3 days" in text
    assert "Enjoy!" in text


def test_format_approval_decided_push_rejected_without_comments_has_no_comments_line():
    text = format_approval_decided_push(subject_summary="Annual Leave: 3 days", final_status="rejected", comments=None)

    assert "Rejected" in text
    assert "Comments" not in text


def test_format_approval_comment_prompt_mentions_decision_word():
    approve_text = format_approval_comment_prompt("approve")
    reject_text = format_approval_comment_prompt("reject")

    assert "approval" in approve_text
    assert "rejection" in reject_text


def test_format_approval_decision_result_for_final_status():
    approved = ApprovalRequest(
        id="req-1", subject_type="leave.leave_request", subject_id="leave-req-1",
        requested_by_employee_id="emp-1", subject_summary="x", status="approved", current_level=1,
    )

    text = format_approval_decision_result(approved)

    assert "Approved" in text


def test_format_approval_step_advanced_push_includes_message_and_summary():
    """Leave review round: the manager-approved/awaiting-HR push — wraps the
    backend's already-composed sentence without inventing any wording of
    its own."""
    text = format_approval_step_advanced_push(
        message="Your manager has approved your leave request. It is now awaiting HR processing.",
        subject_summary="Annual Leave: 2026-09-01 -> 2026-09-03 (3 days)",
    )

    assert "Your manager has approved your leave request. It is now awaiting HR processing." in text
    assert "Annual Leave: 2026-09-01 -> 2026-09-03 (3 days)" in text


def test_format_approval_decision_result_for_advanced_pending_level():
    advanced = ApprovalRequest(
        id="req-1", subject_type="leave.leave_request", subject_id="leave-req-1",
        requested_by_employee_id="emp-1", subject_summary="x", status="pending", current_level=2,
    )

    text = format_approval_decision_result(advanced)

    assert "level 2" in text
