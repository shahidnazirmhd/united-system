"""Transient conversation state for the multi-step "Apply Leave" flow —
the Leave-module equivalent of `auth/account_linking.py`'s OTP-pending
state, same discipline: this is the *only* file in this service that knows
"applying for leave" is a multi-step conversation (pick a type, then a
start date, then an end date, then an optional reason, then confirm).
`handlers/leave_handlers.py` calls this class's public methods and does no
state management of its own.

State lives in Redis, keyed by `telegram_user_id`, short-lived — a stalled
conversation (someone taps "Apply Leave" and then goes quiet) should not
block them from starting fresh indefinitely; it simply expires.

This service does no business validation at all — it only shapes and
carries the conversation forward. Every real business rule (leave type
must exist, sufficient balance, no overlap, valid date range, ...) is
enforced by the backend when `submit()` finally calls
`LeaveEndpoint.apply()`; this class's job ends at "do these look like
dates" (a presentation-layer input shape check, not a business rule — the
same category of validation DRF serializers do on the backend, distinct
from `LeaveValidationService`).
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING

from src.errors import InvalidLeaveDateInputError, NoLeaveApplicationInProgressError
from src.logging_config import log_event

if TYPE_CHECKING:
    import redis.asyncio as redis

    from src.api_client.endpoints.leave import LeaveEndpoint, LeaveRequest

logger = logging.getLogger(__name__)

_KEY_PREFIX = "telegram_gateway:leave_apply:"
# A stalled "apply leave" conversation shouldn't linger forever, but should
# comfortably outlast a moment's distraction while typing dates —
# considerably longer than the OTP flow's 10 minutes (entering three
# separate pieces of information takes longer than copying one code).
_APPLICATION_STATE_TTL = timedelta(minutes=30)

STEP_START_DATE = "start_date"
STEP_END_DATE = "end_date"
STEP_REASON = "reason"
STEP_CONFIRM = "confirm"

_DATE_FORMAT = "%Y-%m-%d"


@dataclass(frozen=True)
class LeaveApplicationState:
    step: str
    leave_type_id: str
    leave_type_name: str
    start_date: str | None = None
    end_date: str | None = None
    reason: str | None = None


def _parse_date_input(text: str) -> str:
    """Accepts YYYY-MM-DD only — deliberately one strict format rather than
    guessing between locales' DD/MM vs MM/DD conventions, which would risk
    silently applying for the wrong dates. Raises InvalidLeaveDateInputError
    (caught by the handler, not this class) with a message the handler can
    show back verbatim."""
    try:
        parsed = datetime.strptime(text.strip(), _DATE_FORMAT).date()
    except ValueError as exc:
        raise InvalidLeaveDateInputError(
            f"'{text.strip()}' doesn't look like a date. Please send it as YYYY-MM-DD, e.g. "
            f"{date.today().isoformat()}."
        ) from exc
    return parsed.isoformat()


class LeaveApplicationService:
    def __init__(self, leave: LeaveEndpoint, redis_client: redis.Redis) -> None:
        self._leave = leave
        self._redis = redis_client

    @staticmethod
    def _key(telegram_user_id: int) -> str:
        return f"{_KEY_PREFIX}{telegram_user_id}"

    async def start(self, *, telegram_user_id: int, leave_type_id: str, leave_type_name: str) -> None:
        """Step 1 (after the employee taps a leave type button)."""
        state = LeaveApplicationState(step=STEP_START_DATE, leave_type_id=leave_type_id, leave_type_name=leave_type_name)
        await self._save(telegram_user_id, state)
        log_event(logger, logging.INFO, "leave_application_started", telegram_user_id=telegram_user_id, leave_type_id=leave_type_id)

    async def get_state(self, telegram_user_id: int) -> LeaveApplicationState | None:
        raw = await self._redis.get(self._key(telegram_user_id))
        if raw is None:
            return None
        data = json.loads(raw)
        return LeaveApplicationState(**data)

    async def is_active(self, telegram_user_id: int) -> bool:
        return await self._redis.exists(self._key(telegram_user_id)) == 1

    async def submit_start_date(self, telegram_user_id: int, text: str) -> LeaveApplicationState:
        state = await self._require_state(telegram_user_id, expected_step=STEP_START_DATE)
        start_date = _parse_date_input(text)
        new_state = LeaveApplicationState(
            step=STEP_END_DATE, leave_type_id=state.leave_type_id, leave_type_name=state.leave_type_name,
            start_date=start_date,
        )
        await self._save(telegram_user_id, new_state)
        return new_state

    async def submit_end_date(self, telegram_user_id: int, text: str) -> LeaveApplicationState:
        state = await self._require_state(telegram_user_id, expected_step=STEP_END_DATE)
        end_date = _parse_date_input(text)
        new_state = LeaveApplicationState(
            step=STEP_REASON, leave_type_id=state.leave_type_id, leave_type_name=state.leave_type_name,
            start_date=state.start_date, end_date=end_date,
        )
        await self._save(telegram_user_id, new_state)
        return new_state

    async def submit_reason(self, telegram_user_id: int, text: str) -> LeaveApplicationState:
        state = await self._require_state(telegram_user_id, expected_step=STEP_REASON)
        reason = None if text.strip().lower() == "skip" else text.strip()
        new_state = LeaveApplicationState(
            step=STEP_CONFIRM, leave_type_id=state.leave_type_id, leave_type_name=state.leave_type_name,
            start_date=state.start_date, end_date=state.end_date, reason=reason,
        )
        await self._save(telegram_user_id, new_state)
        return new_state

    async def submit(self, telegram_user_id: int) -> LeaveRequest:
        """Final step: submits the assembled application to the backend.
        Business-rule failures (insufficient balance, overlap, ...) surface
        as `HRMSAPIError` unchanged — the caller (handlers/leave_handlers.py)
        translates it via `errors.friendly_message_for`, same discipline as
        `AccountLinkingService.complete_linking`. On ANY outcome (success or
        failure) the pending state is cleared: unlike a wrong OTP (worth
        retrying with the same token), a rejected leave application should
        not silently retry with the same stale start command — clearing
        state means the employee simply starts a fresh /apply_leave with a
        clean slate, which is also the correct behavior on success."""
        state = await self._require_state(telegram_user_id, expected_step=STEP_CONFIRM)
        assert state.start_date is not None and state.end_date is not None
        try:
            result = await self._leave.apply(
                telegram_user_id=telegram_user_id,
                leave_type_id=state.leave_type_id,
                start_date=state.start_date,
                end_date=state.end_date,
                reason=state.reason,
            )
        finally:
            await self._redis.delete(self._key(telegram_user_id))
        log_event(logger, logging.INFO, "leave_application_submitted", telegram_user_id=telegram_user_id, leave_request_id=result.id)
        return result

    async def cancel(self, telegram_user_id: int) -> None:
        await self._redis.delete(self._key(telegram_user_id))

    async def _require_state(self, telegram_user_id: int, *, expected_step: str) -> LeaveApplicationState:
        state = await self.get_state(telegram_user_id)
        if state is None or state.step != expected_step:
            raise NoLeaveApplicationInProgressError()
        return state

    async def _save(self, telegram_user_id: int, state: LeaveApplicationState) -> None:
        payload = json.dumps(
            {
                "step": state.step,
                "leave_type_id": state.leave_type_id,
                "leave_type_name": state.leave_type_name,
                "start_date": state.start_date,
                "end_date": state.end_date,
                "reason": state.reason,
            }
        )
        await self._redis.set(self._key(telegram_user_id), payload, ex=int(_APPLICATION_STATE_TTL.total_seconds()))
