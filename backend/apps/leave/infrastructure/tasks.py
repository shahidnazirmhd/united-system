"""Daily Celery Beat task (round 14 items 6/8) — reconciles Employee
Current Status against approved leave requests for leaves that were
approved ahead of their start date, or whose end date has now passed.

This is the first `beat_schedule` entry in the whole codebase — see
`config/celery.py`'s newly-added `app.conf.beat_schedule` and
`infra/docker-compose.yml`'s new `celery_beat` service, both added
alongside this file. Every immediate (same-day) transition is already
handled synchronously by
`apps.leave.application.services.leave_request_service.LeaveRequestService
._sync_status_on_approve`/`_sync_status_on_cancel` — this task exists only
for the future-dated case those two deliberately skip, plus as a safety
net for anything that failed there (see those methods' own docstrings).
"""
from __future__ import annotations

import logging
from datetime import date

import httpx
from celery import shared_task
from django.conf import settings

from apps.leave.infrastructure.employee_lookup_adapter import (
    EmployeeServiceLookupAdapter,
    EmployeeStatusServiceAdapter,
)
from apps.leave.infrastructure.repositories import DjangoLeaveRequestRepository, DjangoLeaveTypeRepository

logger = logging.getLogger(__name__)


@shared_task(name="apps.leave.infrastructure.tasks.reconcile_leave_employee_statuses")
def reconcile_leave_employee_statuses() -> None:
    today = date.today()
    requests = DjangoLeaveRequestRepository()
    leave_types = DjangoLeaveTypeRepository()
    employee_status = EmployeeStatusServiceAdapter()
    employee_lookup = EmployeeServiceLookupAdapter()

    _run_start_pass(today, requests, leave_types, employee_status)
    _run_end_pass(today, requests, employee_lookup, employee_status)


def _run_start_pass(
    today: date,
    requests: DjangoLeaveRequestRepository,
    leave_types: DjangoLeaveTypeRepository,
    employee_status: EmployeeStatusServiceAdapter,
) -> None:
    """Every APPROVED request starting today, whose leave type maps to an
    Employee Current Status, enters that status now. Requests approved
    with a start date that had already arrived (or was backdated) were
    already handled synchronously at approval time
    (`LeaveRequestService._sync_status_on_approve`) — re-running
    `enter_leave_status` for those here is harmless (Employees' own
    `Employee.enter_leave_status` is written to tolerate being called
    again for an employee already on that same status — see its
    `status_before_leave` bookkeeping), not a double-transition bug.
    """
    for leave_request in requests.list_approved_starting_on(today):
        leave_type = leave_types.get_by_id(leave_request.leave_type_id)
        if leave_type is None or leave_type.maps_to_employee_status is None:
            continue
        try:
            employee_status.enter_leave_status(leave_request.employee_id, leave_type.maps_to_employee_status)
        except Exception:
            logger.warning(
                "Daily reconciliation: could not enter leave status for employee=%s "
                "(leave request=%s, status=%s).",
                leave_request.employee_id,
                leave_request.id,
                leave_type.maps_to_employee_status,
                exc_info=True,
            )


def _run_end_pass(
    today: date,
    requests: DjangoLeaveRequestRepository,
    employee_lookup: EmployeeServiceLookupAdapter,
    employee_status: EmployeeStatusServiceAdapter,
) -> None:
    """Every employee currently on a system-managed leave status
    (SICK_LEAVE/ANNUAL_LEAVE) who has no APPROVED request covering today
    at all reverts now — covers both "the leave's end date has passed"
    and "the leave was cancelled after it started and the immediate
    revert at cancel time failed" in one pass, since both cases look
    identical from this query's point of view (no approved leave covers
    today for this employee)."""
    on_leave_status = set(employee_lookup.list_employee_ids_on_leave_status())
    if not on_leave_status:
        return
    still_covered = requests.list_employee_ids_with_approved_leave_covering(today)
    for employee_id in on_leave_status - still_covered:
        try:
            employee_status.exit_leave_status(employee_id)
        except Exception:
            logger.warning(
                "Daily reconciliation: could not exit leave status for employee=%s.",
                employee_id,
                exc_info=True,
            )


# --- Leave cancellation notification (round 15 item 6) --------------------
# Leave's own small, parallel notification channel — deliberately NOT a
# reuse of `apps.approvals.infrastructure.tasks.send_approval_notification`
# (that task's payload is Approval-Engine-specific, requiring a mandatory
# `approval_request_id` a cancellation doesn't have — see
# `apps.leave.application.ports.LeaveNotificationPort`'s docstring for the
# full reasoning). Posts to the SAME Gateway `/internal/notify` endpoint,
# just with a new `notification_type`.
NOTIFICATION_TYPE_LEAVE_CANCELLED = "leave_cancelled"


@shared_task(
    name="apps.leave.infrastructure.tasks.send_leave_cancelled_notification",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def send_leave_cancelled_notification(
    self,
    *,
    chat_id: int,
    leave_request_id: str,
    summary: str,
    was_approved: bool = True,
) -> None:
    if not settings.TELEGRAM_GATEWAY_BASE_URL:
        logger.warning(
            "TELEGRAM_GATEWAY_BASE_URL is not configured — skipping leave cancellation "
            "notification (leave_request_id=%s). Set it to enable Telegram notifications.",
            leave_request_id,
        )
        return

    payload = {
        "chat_id": chat_id,
        "notification_type": NOTIFICATION_TYPE_LEAVE_CANCELLED,
        "leave_request_id": leave_request_id,
        "subject_summary": summary,
        # Round 17 item 3 — lets the Gateway pick the right wording (an
        # already-approved leave being cancelled reads differently from a
        # still-pending request whose approval was closed). Defaults to
        # `True` only so an already-queued task from before this change
        # (mid-deploy) doesn't crash on a missing kwarg; every NEW dispatch
        # (`CeleryLeaveNotificationAdapter.notify_leave_cancelled`) always
        # passes it explicitly.
        "was_approved": was_approved,
    }
    url = f"{settings.TELEGRAM_GATEWAY_BASE_URL.rstrip('/')}/internal/notify"
    try:
        response = httpx.post(
            url,
            json=payload,
            headers={"X-Internal-Service-Key": settings.INTERNAL_SERVICE_API_KEY},
            timeout=settings.TELEGRAM_GATEWAY_NOTIFY_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning(
            "Failed to deliver leave cancellation notification to the Telegram Gateway "
            "(leave_request_id=%s): %s",
            leave_request_id,
            exc,
        )
        raise self.retry(exc=exc)
