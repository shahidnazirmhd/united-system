"""Translates `api_client/endpoints/leave.py` shapes into Telegram message
text — the Leave-module counterpart to `formatting/profile_formatter.py`.
Pure functions, no I/O, reused across `handlers/leave_handlers.py`'s
several commands and callbacks so a display change is a one-file edit.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from src.formatting.common import escape_markdown, field_or_placeholder

if TYPE_CHECKING:
    from src.api_client.endpoints.leave import LeaveBalance, LeaveHistoryPage, LeaveRequest, LeaveType
    from src.auth.leave_application import LeaveApplicationState

_REQUEST_STATUS_LABELS = {
    "draft": "📝 Draft",
    "pending": "🟡 Pending",
    "approved": "🟢 Approved",
    "rejected": "🔴 Rejected",
    "cancelled": "⚫ Cancelled",
}


def _status_label(status: str) -> str:
    return _REQUEST_STATUS_LABELS.get(status, status.replace("_", " ").title())


def format_leave_balances(balances: list[LeaveBalance]) -> str:
    if not balances:
        return "You don't have any leave balances set up yet. Please contact HR."

    lines = ["*Your Leave Balance*\n"]
    for balance in balances:
        name = field_or_placeholder(balance.leave_type_name)
        lines.append(
            f"*{name}* ({balance.year})\n"
            f"  Available: *{balance.available_days}* days\n"
            f"  Entitled: {balance.entitled_days} · Used: {balance.used_days} · "
            f"Carried forward: {balance.carried_forward_days}\n"
            f"  Pending requests: {balance.pending_days} days"
        )
    return "\n\n".join(lines)


def format_leave_types_prompt() -> str:
    return "Which leave type would you like to apply for?"


def format_leave_type_button_label(leave_type: LeaveType) -> str:
    return f"{leave_type.name} ({leave_type.default_annual_days}d/yr)"


def format_leave_request_summary_line(request: LeaveRequest) -> str:
    """One line per request — used both in the /leave_history list and as
    button labels in the /cancel_leave selection keyboard."""
    name = field_or_placeholder(request.leave_type_name)
    return f"{name}: {request.start_date} → {request.end_date} ({request.total_days}d) — {_status_label(request.status)}"


def format_leave_history(page: LeaveHistoryPage) -> str:
    if not page.items:
        return "You don't have any leave requests yet. Send /apply_leave to create one."

    lines = ["*Your Leave History*\n"]
    for request in page.items:
        lines.append(f"• {escape_markdown(format_leave_request_summary_line(request))}\n  ID: `{request.id}`")
    lines.append(f"\nPage {page.page} of {max(page.total_pages, 1)} — {page.total_count} total request(s).")
    return "\n".join(lines)


def format_leave_request_detail(request: LeaveRequest) -> str:
    lines = [
        "*Leave Request Details*",
        f"🏷️ Type: {field_or_placeholder(request.leave_type_name)}",
        f"📅 Dates: {request.start_date} → {request.end_date} ({request.total_days} day(s))",
        f"📋 Status: {_status_label(request.status)}",
        f"📝 Reason: {field_or_placeholder(request.reason)}",
    ]
    if request.status == "approved":
        lines.append(f"✅ Approved: {field_or_placeholder(request.decided_at)}")
    if request.status == "rejected":
        lines.append(f"❌ Rejected: {field_or_placeholder(request.decided_at)}")
        lines.append(f"💬 Comments: {field_or_placeholder(request.decision_comments)}")
    if request.status == "cancelled":
        lines.append(f"🚫 Cancelled: {field_or_placeholder(request.cancelled_at)}")
        lines.append(f"💬 Reason: {field_or_placeholder(request.cancellation_reason)}")
    return "\n".join(lines)


def format_apply_leave_prompt_start_date() -> str:
    return "Got it. What's the *start date*? Send it as YYYY-MM-DD."


def format_apply_leave_prompt_end_date() -> str:
    return "And the *end date*? Send it as YYYY-MM-DD."


def format_apply_leave_prompt_reason() -> str:
    return 'Want to add a reason? Send it, or reply "skip".'


def format_apply_leave_confirmation(state: LeaveApplicationState) -> str:
    reason_line = f"📝 Reason: {state.reason}" if state.reason else "📝 Reason: _(none)_"
    return (
        "*Please confirm your leave application:*\n\n"
        f"🏷️ Type: {escape_markdown(state.leave_type_name)}\n"
        f"📅 Dates: {state.start_date} → {state.end_date}\n"
        f"{reason_line}"
    )


def format_leave_applied(request: LeaveRequest) -> str:
    return (
        f"✅ Your leave request has been submitted and is *{_status_label(request.status)}*.\n"
        f"📅 {request.start_date} → {request.end_date} ({request.total_days} day(s))\n"
        f"ID: `{request.id}`"
    )


def format_leave_cancelled(request: LeaveRequest) -> str:
    return f"🚫 Leave request `{request.id}` has been cancelled."


def format_no_cancellable_requests() -> str:
    return "You don't have any pending or approved leave requests to cancel."


def format_cancel_leave_prompt() -> str:
    return "Which leave request would you like to cancel?"


def format_cancel_leave_confirm_prompt(request: LeaveRequest) -> str:
    return f"Cancel this request?\n\n{format_leave_request_summary_line(request)}"
