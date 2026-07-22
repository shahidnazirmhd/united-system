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

import logging
from contextlib import asynccontextmanager

import redis.asyncio as redis
from fastapi import FastAPI, Header, HTTPException, Request

from src.api_client.endpoints.employees import EmployeesEndpoint
from src.api_client.endpoints.leave import LeaveEndpoint
from src.api_client.hrms_client import HRMSClient
from src.auth.account_linking import AccountLinkingService
from src.auth.leave_application import LeaveApplicationService
from src.config import Settings
from src.errors import InvalidWebhookSignatureError
from src.handlers.registry import registry
from src.logging_config import configure_logging, log_event
from src.telegram_client.bot_api_client import BotAPIClient
from src.telegram_client.types import TelegramUpdate
from src.webhook.rate_limiter import RateLimiter
from src.webhook.security import verify_webhook_secret
from src.webhook.update_router import Dependencies, route

logger = logging.getLogger(__name__)


def create_app(settings: Settings) -> FastAPI:
    configure_logging(settings.log_level)

    # Importing these triggers every handler's @registry.command/@registry.callback
    # decorator to run — see main.py's docstring for why this import is
    # deliberately here (or in main.py) and not somewhere less obvious.
    from src.handlers import (  # noqa: F401
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
        linking_service = AccountLinkingService(employees_endpoint, redis_client)
        leave_application_service = LeaveApplicationService(leave_endpoint, redis_client)
        rate_limiter = RateLimiter(redis_client, limit_per_window=settings.rate_limit_per_chat_per_minute)

        state["deps"] = Dependencies(
            bot=bot,
            linking=linking_service,
            employees=employees_endpoint,
            leave=leave_endpoint,
            leave_application=leave_application_service,
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
