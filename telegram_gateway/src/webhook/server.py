"""The single HTTP entrypoint Telegram's servers call on every incoming
message — per HRMS_Folder_Structure.md section 3.1, "the only inbound
network surface this service exposes."

`create_app` is the composition root for the whole service: every
concrete dependency (HTTP clients, Redis connections, the command registry)
is constructed exactly once here and threaded through
`webhook/update_router.Dependencies` — the same "one composition root, no
DI framework" discipline as the backend's `interface/dependencies.py` files,
adapted to FastAPI's lifespan/dependency-injection idioms.
"""
from __future__ import annotations

import hmac
import logging
from contextlib import asynccontextmanager

import redis.asyncio as redis
from fastapi import FastAPI, Header, HTTPException, Request

from src.api_client.endpoints.approvals import ApprovalsEndpoint
from src.api_client.endpoints.employees import EmployeesEndpoint
from src.api_client.endpoints.leave import LeaveEndpoint
from src.api_client.hrms_client import HRMSClient
from src.auth.account_linking import AccountLinkingService
from src.auth.approval_decision import ApprovalDecisionService
from src.auth.leave_application import LeaveApplicationService
from src.config import Settings
from src.errors import InvalidWebhookSignatureError
from src.formatting.approval_formatter import (
    format_approval_decided_push,
    format_approval_requested_push,
    format_approval_step_advanced_push,
)
from src.formatting.leave_formatter import format_leave_cancelled_push
from src.formatting.keyboards import build_approval_decision_keyboard
from src.handlers.registry import registry
from src.logging_config import configure_logging, log_event
from src.telegram_client.bot_api_client import BotAPIClient
from src.telegram_client.types import TelegramUpdate
from src.webhook.rate_limiter import RateLimiter
from src.webhook.security import verify_webhook_secret
from src.webhook.update_router import Dependencies, route

logger = logging.getLogger(__name__)

_NOTIFICATION_TYPE_REQUESTED = "approval_requested"
_NOTIFICATION_TYPE_DECIDED = "approval_decided"
_NOTIFICATION_TYPE_STEP_ADVANCED = "approval_step_advanced"
# Round 15 item 6 — Leave's own notification channel (not routed through
# the Approval Engine's three types above; see
# apps.leave.application.ports.LeaveNotificationPort's docstring).
_NOTIFICATION_TYPE_LEAVE_CANCELLED = "leave_cancelled"


def create_app(settings: Settings) -> FastAPI:
    configure_logging(settings.log_level)

    # Importing these triggers every handler's @registry.command/@registry.callback
    # decorator to run — see main.py's docstring for why this import is
    # deliberately here (or in main.py) and not somewhere less obvious.
    from src.handlers import (  # noqa: F401
        approval_handlers,
        help_handler,
        leave_handlers,
        link_handler,
        profile_handler,
        start_handler,
        status_handler,
    )

    state: dict[str, object] = {}

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        redis_client = redis.from_url(settings.redis_url, decode_responses=False)
        bot = BotAPIClient(settings.bot_token, timeout_seconds=settings.hrms_api_timeout_seconds)
        hrms_client = HRMSClient(
            settings.hrms_api_base_url,
            internal_service_key=settings.internal_api_key,
            timeout_seconds=settings.hrms_api_timeout_seconds,
        )
        employees_endpoint = EmployeesEndpoint(hrms_client)
        leave_endpoint = LeaveEndpoint(hrms_client)
        approvals_endpoint = ApprovalsEndpoint(hrms_client)
        linking_service = AccountLinkingService(employees_endpoint, redis_client)
        leave_application_service = LeaveApplicationService(leave_endpoint, redis_client)
        approval_decision_service = ApprovalDecisionService(approvals_endpoint, redis_client)
        rate_limiter = RateLimiter(redis_client, limit_per_window=settings.rate_limit_per_chat_per_minute)

        state["deps"] = Dependencies(
            bot=bot,
            linking=linking_service,
            employees=employees_endpoint,
            leave=leave_endpoint,
            leave_application=leave_application_service,
            approvals=approvals_endpoint,
            approval_decision=approval_decision_service,
        )
        state["rate_limiter"] = rate_limiter
        state["redis"] = redis_client
        state["bot"] = bot
        state["hrms_client"] = hrms_client

        log_event(logger, logging.INFO, "gateway_started", environment=settings.environment)
        try:
            yield
        finally:
            await bot.aclose()
            await hrms_client.aclose()
            await redis_client.aclose()
            log_event(logger, logging.INFO, "gateway_stopped")

    app = FastAPI(title="United HRMS — Telegram Gateway", lifespan=lifespan)

    @app.get("/healthz")
    async def healthz() -> dict:
        """Liveness/readiness probe. Deliberately does not check
        connectivity to the HRMS backend or Redis — per HRMS_Architecture.md's
        general health-check convention (see backend's own `healthcheck`
        app), liveness answers "is this process able to serve requests,"
        not "are my dependencies currently up.\""""
        return {"status": "ok"}

    @app.post("/internal/notify")
    async def internal_notify(
        request: Request,
        x_internal_service_key: str | None = Header(default=None),
    ) -> dict:
        """The first-ever backend->Gateway call direction (see
        `apps.approvals.infrastructure.tasks.send_approval_notification` on
        the Django side). Authenticated with the same static shared secret
        (`INTERNAL_SERVICE_API_KEY`) this Gateway already sends *to* the
        backend on every outbound call — proving "this caller really is
        the trusted backend," the exact mirror image of
        `shared_kernel.api.permissions.HasInternalServiceKey`'s own
        reasoning on the Django side, just running in the opposite
        direction. This endpoint does no HR data lookups of its own — the
        backend has already resolved `chat_id` (via
        `apps.approvals.application.ports.EmployeeLookupPort
        .get_telegram_chat_id`) before calling here, so this Gateway only
        ever builds Telegram-specific text/keyboard and sends it.
        """
        expected = settings.internal_api_key
        if not expected or not x_internal_service_key or not hmac.compare_digest(
            x_internal_service_key, expected
        ):
            log_event(logger, logging.WARNING, "internal_notify_rejected")
            raise HTTPException(status_code=403, detail="Invalid internal service key")

        payload = await request.json()
        notification_type = payload.get("notification_type")
        chat_id = payload.get("chat_id")
        subject_summary = payload.get("subject_summary", "")
        bot: BotAPIClient = state["bot"]  # type: ignore[assignment]

        if notification_type == _NOTIFICATION_TYPE_REQUESTED:
            text = format_approval_requested_push(subject_summary=subject_summary, level=payload.get("level") or 1)
            await bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=build_approval_decision_keyboard(payload.get("approval_request_id", "")),
            )
        elif notification_type == _NOTIFICATION_TYPE_DECIDED:
            text = format_approval_decided_push(
                subject_summary=subject_summary,
                final_status=payload.get("final_status") or "",
                comments=payload.get("comments"),
            )
            await bot.send_message(chat_id=chat_id, text=text)
        elif notification_type == _NOTIFICATION_TYPE_STEP_ADVANCED:
            # Leave review round: a NON-final decision (e.g. the manager
            # approving) that moved the chain to a further level — never
            # sent for a final decision, which is `_NOTIFICATION_TYPE_DECIDED`
            # above. `message` is the complete sentence the backend's
            # subject module already composed (see
            # `format_approval_step_advanced_push`'s docstring); no inline
            # Approve/Reject keyboard here, since this requester isn't the
            # one who needs to act next.
            text = format_approval_step_advanced_push(
                message=payload.get("message") or "", subject_summary=subject_summary
            )
            await bot.send_message(chat_id=chat_id, text=text)
        elif notification_type == _NOTIFICATION_TYPE_LEAVE_CANCELLED:
            # Round 15 item 6 — `subject_summary` here is Leave's own
            # already-composed sentence (see
            # `LeaveRequestService._notify_leave_cancelled`), not the
            # Approval Engine's; no inline keyboard, this is a one-way
            # notice, not something to act on.
            # Round 17 item 3 — `was_approved` (defaults to `True` if the
            # backend didn't send it, matching the payload's own
            # backward-compatible default in
            # `apps.leave.infrastructure.tasks.send_leave_cancelled_notification`)
            # picks the right wording for an already-approved cancellation
            # vs. a still-pending one whose approval was closed.
            text = format_leave_cancelled_push(
                subject_summary=subject_summary, was_approved=payload.get("was_approved", True)
            )
            await bot.send_message(chat_id=chat_id, text=text)
        else:
            log_event(logger, logging.WARNING, "internal_notify_unknown_type", notification_type=notification_type)
            raise HTTPException(status_code=422, detail="Unknown notification_type")

        return {"ok": True}

    @app.post(settings.webhook_path)
    async def telegram_webhook(
        request: Request,
        x_telegram_bot_api_secret_token: str | None = Header(default=None),
    ) -> dict:
        try:
            verify_webhook_secret(x_telegram_bot_api_secret_token, settings.webhook_secret_token)
        except InvalidWebhookSignatureError:
            log_event(logger, logging.WARNING, "webhook_signature_rejected")
            raise HTTPException(status_code=401, detail="Invalid webhook signature")

        payload = await request.json()
        update = TelegramUpdate.model_validate(payload)

        rate_limiter: RateLimiter = state["rate_limiter"]  # type: ignore[assignment]
        if update.chat_id is not None and not await rate_limiter.is_allowed(update.chat_id):
            log_event(logger, logging.WARNING, "rate_limit_exceeded", chat_id=update.chat_id)
            # Acknowledge with 200 regardless — Telegram retries (with
            # backoff) on non-2xx responses, which would only make a flood
            # worse. Silently dropping the update is the correct response
            # to a rate-limited sender, not an error surfaced to Telegram.
            return {"ok": True}

        deps: Dependencies = state["deps"]  # type: ignore[assignment]
        await route(update, deps, registry)
        return {"ok": True}

    return app
