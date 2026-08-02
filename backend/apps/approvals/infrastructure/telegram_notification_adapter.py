"""Concrete `ApprovalNotificationPort` implementation: dispatches a Celery
task that calls the Telegram Gateway's own internal notify endpoint.

This is the ONE file in this module that "knows" notifications happen to
end up in Telegram — and even here, only in the sense of "dispatch a task
by name"; the actual Telegram formatting (message text, inline
Approve/Reject buttons) is built entirely by the Gateway itself
(`telegram_gateway/src/handlers/approval_handlers.py`), never by this
backend. `ApprovalService` (application layer) only ever depends on the
`ApprovalNotificationPort` interface — swapping Telegram for email/SMS/web
push later is a change to this one file and `infrastructure/tasks.py`,
never to `ApprovalService` or any subject module.
"""
from __future__ import annotations

import uuid

from apps.approvals.application.ports import ApprovalNotificationPort, EmployeeLookupPort
from apps.approvals.infrastructure.tasks import send_approval_notification
from shared_kernel.infrastructure.celery_dispatcher import dispatch

NOTIFICATION_TYPE_REQUESTED = "approval_requested"
NOTIFICATION_TYPE_DECIDED = "approval_decided"
NOTIFICATION_TYPE_STEP_ADVANCED = "approval_step_advanced"


class CeleryTelegramNotificationAdapter(ApprovalNotificationPort):
    def __init__(self, employee_lookup: EmployeeLookupPort) -> None:
        self._employees = employee_lookup

    def notify_approval_requested(
        self,
        *,
        approver_employee_id: uuid.UUID,
        subject_summary: str,
        approval_request_id: uuid.UUID,
        level: int,
    ) -> None:
        chat_id = self._employees.get_telegram_chat_id(approver_employee_id)
        if chat_id is None:
            # The subject module's own pre-flight validation (e.g.
            # apps.leave.domain.exceptions.ManagerNotLinkedToTelegramError)
            # is what's supposed to prevent this — a missing chat_id here
            # means the approver unlinked Telegram between request creation
            # and this notification being dispatched. Not fatal to the
            # approval request itself (it still exists and is still
            # decidable via the self-service REST API), only the Telegram
            # nudge is skipped — logged by the Celery task itself.
            return
        dispatch(
            send_approval_notification,
            chat_id=chat_id,
            notification_type=NOTIFICATION_TYPE_REQUESTED,
            approval_request_id=str(approval_request_id),
            subject_summary=subject_summary,
            level=level,
            final_status=None,
            comments=None,
            message=None,
        )

    def notify_decision_made(
        self,
        *,
        requested_by_employee_id: uuid.UUID,
        subject_summary: str,
        final_status: str,
        comments: str | None,
        approval_request_id: uuid.UUID,
    ) -> None:
        chat_id = self._employees.get_telegram_chat_id(requested_by_employee_id)
        if chat_id is None:
            return
        dispatch(
            send_approval_notification,
            chat_id=chat_id,
            notification_type=NOTIFICATION_TYPE_DECIDED,
            approval_request_id=str(approval_request_id),
            subject_summary=subject_summary,
            level=None,
            final_status=final_status,
            comments=comments,
            message=None,
        )

    def notify_step_advanced(
        self,
        *,
        requested_by_employee_id: uuid.UUID,
        subject_summary: str,
        message: str,
        new_level: int,
        approval_request_id: uuid.UUID,
    ) -> None:
        chat_id = self._employees.get_telegram_chat_id(requested_by_employee_id)
        if chat_id is None:
            return
        dispatch(
            send_approval_notification,
            chat_id=chat_id,
            notification_type=NOTIFICATION_TYPE_STEP_ADVANCED,
            approval_request_id=str(approval_request_id),
            subject_summary=subject_summary,
            level=new_level,
            final_status=None,
            comments=None,
            message=message,
        )
