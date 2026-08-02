"""The first real Celery task in this codebase.

`config/celery.py`'s own docstring anticipated exactly this moment ("no
module has background tasks yet" — see that file's routing-convention
comment). `shared_kernel/infrastructure/event_bus_impl.py`'s docstring
anticipated it too ("needed once Approvals/Notifications need it").

Sends one HTTP call to the Telegram Gateway's `POST /internal/notify` —
the first ever backend->Gateway call direction (every prior integration was
Gateway calling this backend). Authenticated with the same
`INTERNAL_SERVICE_API_KEY` static shared secret the Gateway already sends
*to* this backend on every request — see
`config/settings/base.py`'s "Approval Engine (Phase 9)" section.

Deliberately thin: this task does no Telegram-specific formatting of its
own (no emoji, no inline keyboard layout) — it forwards exactly the
structured fields `ApprovalService`/`CeleryTelegramNotificationAdapter`
gathered, and the Gateway (which owns all Telegram-specific presentation,
per HRMS_Folder_Structure.md) decides what to actually show and which
buttons to attach. This keeps the backend permanently ignorant of
Telegram's UI concerns, matching "no business logic in Telegram Gateway"
applied in the opposite direction: no Telegram *presentation* logic in the
backend either. The one exception (Leave review round): `message`, for
`NOTIFICATION_TYPE_STEP_ADVANCED` only, carries a complete, already-composed
sentence rather than structured fields the Gateway assembles — that
sentence is itself opaque subject-module content (see
`ApproverAssignment.requester_notification_message`'s docstring), no
different in kind from `subject_summary` above; the Gateway still owns
whether/how to wrap it in presentation chrome.
"""
from __future__ import annotations

import logging

import httpx
from celery import shared_task
from django.conf import settings

logger = logging.getLogger(__name__)


@shared_task(
    name="apps.approvals.infrastructure.tasks.send_approval_notification",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def send_approval_notification(
    self,
    *,
    chat_id: int,
    notification_type: str,
    approval_request_id: str,
    subject_summary: str,
    level: int | None,
    final_status: str | None,
    comments: str | None,
    message: str | None = None,
) -> None:
    if not settings.TELEGRAM_GATEWAY_BASE_URL:
        logger.warning(
            "TELEGRAM_GATEWAY_BASE_URL is not configured — skipping approval notification "
            "(approval_request_id=%s, notification_type=%s). Set it to enable Telegram notifications.",
            approval_request_id,
            notification_type,
        )
        return

    payload = {
        "chat_id": chat_id,
        "notification_type": notification_type,
        "approval_request_id": approval_request_id,
        "subject_summary": subject_summary,
        "level": level,
        "final_status": final_status,
        "comments": comments,
        # Leave review round: an opaque, already-composed sentence for
        # `NOTIFICATION_TYPE_STEP_ADVANCED` (e.g. "Your manager has approved
        # your leave request. It is now awaiting HR processing.") — see
        # `ApproverAssignment.requester_notification_message`. `None` for
        # every other notification_type; the Gateway is still the one
        # deciding presentation (emoji, layout), it just has nothing of its
        # own to compose here since the whole sentence already arrived.
        "message": message,
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
            "Failed to deliver approval notification to the Telegram Gateway "
            "(approval_request_id=%s, notification_type=%s): %s",
            approval_request_id,
            notification_type,
            exc,
        )
        raise self.retry(exc=exc)
