"""Concrete `LeaveNotificationPort` implementation: dispatches a Celery task
that calls the Telegram Gateway's own internal notify endpoint — mirrors
`apps.approvals.infrastructure.telegram_notification_adapter
.CeleryTelegramNotificationAdapter`'s exact shape, just for Leave's own
smaller, single-method port. See `LeaveNotificationPort`'s docstring for
why this is a separate channel rather than a reuse of Approvals'.
"""
from __future__ import annotations

import uuid

from apps.leave.application.ports import EmployeeLookupPort, LeaveNotificationPort
from apps.leave.infrastructure.tasks import send_leave_cancelled_notification
from shared_kernel.infrastructure.celery_dispatcher import dispatch


class CeleryLeaveNotificationAdapter(LeaveNotificationPort):
    def __init__(self, employee_lookup: EmployeeLookupPort) -> None:
        self._employees = employee_lookup

    def notify_leave_cancelled(
        self, *, employee_id: uuid.UUID, leave_request_id: uuid.UUID, summary: str, was_approved: bool
    ) -> None:
        chat_id = self._employees.get_telegram_chat_id(employee_id)
        if chat_id is None:
            # The employee has no linked Telegram account (or unlinked it
            # since applying) — not an error, just nothing to push to. The
            # cancellation itself already succeeded before this is called.
            return
        dispatch(
            send_leave_cancelled_notification,
            chat_id=chat_id,
            leave_request_id=str(leave_request_id),
            summary=summary,
            was_approved=was_approved,
        )
