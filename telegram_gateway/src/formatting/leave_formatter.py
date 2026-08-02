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
    button labels in the /cancel_leave selection keyboard. Round 15 item 2:
    shows both total calendar days and working days (excludes the
    configured week-off/holidays)."""
    name = field_or_placeholder(request.leave_type_name)
    return (
        f"{name}: {request.start_date} → {request.end_date} "
        f"({request.total_days}d total, {request.working_days}d working) — {_status_label(request.status)}"
    )


def format_leave_history(page: LeaveHistoryPage) -> str:
    if not page.items:
        return "No leave history found."

    lines = ["*Your Leave History*\n"]
    for request in page.items:
        lines.append(f"• {escape_markdown(format_leave_request_summary_line(request))}\n  ID: `{request.id}`")
    lines.append(f"\nPage {page.page} of {max(page.total_pages, 1)} — {page.total_count} total request(s).")
    return "\n".join(lines)


def format_leave_request_detail(request: LeaveRequest) -> str:
    lines = [
        "*Leave Request Details*",
        f"🏷️ Type: {field_or_placeholder(request.leave_type_name)}",
        f"📅 Dates: {request.start_date} → {request.end_date}",
        f"🗓️ Total days: {request.total_days} · Working days: {request.working_days}",
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


def format_apply_leave_header_start_date() -> str:
    """The From-date calendar's message text (shown above the whole
    keyboard — Telegram always renders a message's `text` above any
    `reply_markup` attached to it, with no way to place text after
    buttons). Deliberately short and generic: the actual "select a date"
    instruction, plus the visual From/To indicator, live in the calendar's
    own footer label instead — see format_apply_leave_footer_start_date —
    positioned below the day grid and above Cancel, not above it."""
    return "🏖️ *Apply Leave*"


def format_apply_leave_footer_start_date() -> str:
    """Plain text — Telegram button labels don't render Markdown — shown
    as the From-date calendar's own last row before Cancel. Doubles as the
    visual indicator of which date is currently being picked (🟢 = From),
    per handlers/calendar_widget.py's `label` mechanism."""
    return "🟢 FROM DATE — tap a day to select"


def format_apply_leave_header_end_date(*, from_date: str | None = None) -> str:
    """`from_date` (ISO string), when known, is echoed back as the To-date
    calendar's message text — this is real message text (unlike the
    footer label below), so it can use Markdown — so the employee can
    always see what they already picked while choosing the To date. Falls
    back to the same generic header as the From-date step if, defensively,
    no From date is known yet (should be unreachable in practice — see
    handlers/leave_handlers.py's dynamic calendar prompt for this purpose,
    the only caller)."""
    if from_date is None:
        return format_apply_leave_header_start_date()
    return f"✅ *From date:* {from_date}"


def format_apply_leave_footer_end_date() -> str:
    """See format_apply_leave_footer_start_date — same mechanism, 🔵 = To."""
    return "🔵 TO DATE — tap a day to select"


def format_apply_leave_prompt_reason(*, from_date: str | None = None, to_date: str | None = None) -> str:
    """`from_date`/`to_date`, when known, are echoed back as a recap so the
    employee can see both picked dates before typing a reason — the last
    checkpoint before the confirmation summary below."""
    prompt = 'Want to add a reason? Send it, or reply "skip".'
    if from_date is None or to_date is None:
        return prompt
    return f"✅ *From date:* {from_date}\n✅ *To date:* {to_date}\n\n{prompt}"


def format_apply_leave_confirmation(state: LeaveApplicationState) -> str:
    reason_line = f"📝 Reason: {state.reason}" if state.reason else "📝 Reason: _(none)_"
    return (
        "*Please confirm your leave application:*\n\n"
        f"🏷️ Type: {escape_markdown(state.leave_type_name)}\n"
        f"📅 From: {state.start_date}\n"
        f"📅 To: {state.end_date}\n"
        f"{reason_line}"
    )


def format_leave_applied(request: LeaveRequest) -> str:
    return (
        f"✅ Your leave request has been submitted and is *{_status_label(request.status)}*.\n"
        f"📅 {request.start_date} → {request.end_date}\n"
        f"🗓️ Total days: {request.total_days} · Working days: {request.working_days}\n"
        f"ID: `{request.id}`"
    )


def format_leave_cancelled(request: LeaveRequest) -> str:
    return f"🚫 Leave request `{request.id}` has been cancelled."


def format_leave_cancelled_push(*, subject_summary: str, was_approved: bool = True) -> str:
    """Round 15 item 6 / round 17 item 3 — the server-pushed notice sent
    whenever a leave request is cancelled (by the employee, HR, or a
    manager), as opposed to `format_leave_cancelled` above, which is the
    synchronous reply to the employee's own /cancel_leave action in this
    same chat. `subject_summary` is the already-composed sentence from
    `LeaveRequestService._notify_leave_cancelled` (leave type, dates, total
    + working days — round 15 item 2), escaped here since (unlike
    `format_leave_history`'s per-line escaping) this is the only place this
    particular string is rendered.

    `was_approved` (round 17 item 3) picks the right wording for each
    action: a leave that was already APPROVED had its balance restored, so
    the recipient is told that explicitly; a still-PENDING request instead
    had its open approval process closed (round 17 item 2) — telling the
    recipient the balance line would be misleading, since nothing was ever
    deducted for a request that was never approved."""
    if was_approved:
        return f"🚫 *Your approved leave has been cancelled.*\n{escape_markdown(subject_summary)}"
    return (
        "🚫 *Your leave request has been cancelled.*\n"
        "Its pending approval process has been closed — no further action is needed.\n"
        f"{escape_markdown(subject_summary)}"
    )


def format_no_cancellable_requests() -> str:
    return "You don't have any pending or approved leave requests to cancel."


def format_cancel_leave_prompt() -> str:
    return "Which leave request would you like to cancel?"


def format_cancel_leave_confirm_prompt(request: LeaveRequest) -> str:
    return f"Cancel this request?\n\n{format_leave_request_summary_line(request)}"
