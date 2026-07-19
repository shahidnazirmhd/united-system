"""Implements the one-time registration/link flow: Employee ID -> OTP ->
Telegram ID stored directly on the Employee record.

Employee & Telegram Authentication refactor: this service no longer issues
or stores any credential of its own (no TokenStore, no SessionManager —
both deleted). There is nothing to "sign in" to: the backend stores the
Telegram user id directly on the Employee record
(apps/employees/domain/entities.py Employee.link_telegram), and every
future request simply presents that same telegram_user_id again. This
class's only remaining state is transient and local — "is this chat
currently waiting for an OTP reply" — everything else (is this Telegram
account linked, and to whom) is asked of the backend fresh every time via
`EmployeesEndpoint.get_link_status`/`get_profile`, never cached here. That
is a deliberate simplification, not just a smaller version of the old
design: the backend's Employee table is the single source of truth for
link state, full stop.

This is the *only* file in this service that knows a "linking flow" is a
two-step conversation (employee code, then a follow-up OTP message) — that
conversational state lives here, in Redis, keyed by `telegram_user_id`,
short-lived (matches the backend's own LINK_OTP_LIFETIME in
apps/employees/application/services/employee_telegram_linking_service.py
so this service's idea of "still waiting for an OTP" never outlives the
backend's idea of "this OTP is still valid"). `handlers/link_handler.py`
calls this class's public methods and does no state management of its own.
"""
from __future__ import annotations

import json
import logging
from datetime import timedelta
from typing import TYPE_CHECKING

from src.errors import HRMSAPIError, LinkingInProgressConflictError, NoLinkingInProgressError
from src.logging_config import log_event

if TYPE_CHECKING:
    # Type hints only — this service's own `self._redis` is used purely via
    # its async get/set/delete/exists methods (duck typing), so no concrete
    # redis package needs to be importable for this class's actual logic
    # (the two-step linking flow) to be unit tested with a fake.
    import redis.asyncio as redis

    from src.api_client.endpoints.employees import EmployeeProfile, EmployeesEndpoint

logger = logging.getLogger(__name__)

_KEY_PREFIX = "telegram_gateway:linking:"
# Mirrors apps/employees/application/services/employee_telegram_linking_service.py's
# LINK_OTP_LIFETIME — this service's "still waiting" window should never
# outlive the backend's actual OTP validity, or a user could be told "enter
# your code" past the point the backend would already reject it as expired.
_LINKING_STATE_TTL = timedelta(minutes=10)


class AccountLinkingService:
    def __init__(self, employees: EmployeesEndpoint, redis_client: redis.Redis) -> None:
        self._employees = employees
        self._redis = redis_client

    @staticmethod
    def _key(telegram_user_id: int) -> str:
        return f"{_KEY_PREFIX}{telegram_user_id}"

    async def is_linked(self, telegram_user_id: int) -> bool:
        status = await self._employees.get_link_status(telegram_user_id=telegram_user_id)
        return status.is_linked

    async def start_linking(
        self, *, employee_code: str, telegram_user_id: int, chat_id: int, telegram_username: str | None
    ) -> None:
        """Step 1: validates the employee code against the backend and
        dispatches an OTP to every email the employee has on file (work
        email always, personal email too if set — see EMPLOYEE_API.md's
        Telegram linking section). Raises
        HRMSAPIError (code="employee_not_found", etc.) unchanged —
        `handlers/link_handler.py` translates it via
        `errors.friendly_message_for`, this method doesn't soften it."""
        existing = await self._redis.get(self._key(telegram_user_id))
        if existing is not None:
            raise LinkingInProgressConflictError()

        await self._employees.request_link(
            employee_code=employee_code,
            telegram_user_id=telegram_user_id,
            chat_id=chat_id,
            telegram_username=telegram_username,
        )

        state = json.dumps({"employee_code": employee_code, "chat_id": chat_id})
        await self._redis.set(self._key(telegram_user_id), state, ex=int(_LINKING_STATE_TTL.total_seconds()))
        log_event(logger, logging.INFO, "linking_started", telegram_user_id=telegram_user_id)

    async def is_awaiting_otp(self, telegram_user_id: int) -> bool:
        return await self._redis.exists(self._key(telegram_user_id)) == 1

    async def complete_linking(
        self, *, telegram_user_id: int, chat_id: int, otp: str, telegram_username: str | None
    ) -> EmployeeProfile:
        """Step 2: verifies the submitted OTP. On success, the backend has
        already stored the Telegram id on the Employee record — this
        method's only remaining job is clearing the local "awaiting OTP"
        flag and handing back the now-linked profile so the handler can
        greet the employee by name. On failure (wrong/expired OTP), the
        pending state is deliberately left in place so the employee can
        simply retry typing the correct code without re-running /link, up
        to the backend's own OTP expiry. The one exception is
        too_many_otp_attempts: the backend has permanently locked that
        specific token at that point (see MAX_OTP_ATTEMPTS in
        apps/employees/application/services/employee_telegram_linking_service.py),
        so leaving our own "awaiting OTP" flag in place would only make the
        employee's next /link bounce off LinkingInProgressConflictError
        ("wait a few minutes") for something that's already dead — clearing
        it here means /link works immediately instead."""
        state_raw = await self._redis.get(self._key(telegram_user_id))
        if state_raw is None:
            raise NoLinkingInProgressError()

        try:
            profile = await self._employees.verify_link(
                telegram_user_id=telegram_user_id,
                chat_id=chat_id,
                otp=otp,
                telegram_username=telegram_username,
            )
        except HRMSAPIError as exc:
            log_event(
                logger, logging.WARNING, "linking_otp_rejected", telegram_user_id=telegram_user_id, code=exc.code
            )
            if exc.code == "too_many_otp_attempts":
                await self._redis.delete(self._key(telegram_user_id))
            raise

        await self._redis.delete(self._key(telegram_user_id))
        log_event(logger, logging.INFO, "linking_completed", telegram_user_id=telegram_user_id)
        return profile

    async def unlink(self, *, telegram_user_id: int) -> None:
        await self._employees.unlink(telegram_user_id=telegram_user_id)
        # Also clears any stale "awaiting OTP" flag, in case /unlink is
        # sent mid-flow — harmless no-op via Redis DEL if none is set.
        await self._redis.delete(self._key(telegram_user_id))
        log_event(logger, logging.INFO, "account_unlinked", telegram_user_id=telegram_user_id)
