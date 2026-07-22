"""Unit tests for auth/leave_application.py's LeaveApplicationService — the
multi-step "Apply Leave" conversation (type -> start date -> end date ->
reason -> confirm -> submit). Start/end dates are supplied as `date`
objects throughout, matching how handlers/leave_handlers.py's calendar
resume handlers actually call this service — there is no free-text date
parsing left in this class at all (see handlers/calendar_widget.py)."""
from __future__ import annotations

from datetime import date

import pytest

from src.api_client.endpoints.leave import LeaveRequest
from src.auth.leave_application import (
    STEP_CONFIRM,
    STEP_END_DATE,
    STEP_REASON,
    STEP_START_DATE,
    LeaveApplicationService,
)
from src.errors import NoLeaveApplicationInProgressError
from tests.fakes import FakeLeaveEndpoint, FakeRedis, make_hrms_error

_APPLIED_REQUEST = LeaveRequest(
    id="req-1", employee_id="emp-1", leave_type_id="lt-1", leave_type_name="Annual Leave",
    start_date="2026-09-01", end_date="2026-09-03", total_days="3.00", reason=None, status="pending",
    approved_by=None, decided_at=None, decision_comments=None, cancelled_at=None, cancellation_reason=None,
)


def _service(leave=None, redis=None) -> LeaveApplicationService:
    return LeaveApplicationService(leave or FakeLeaveEndpoint(), redis or FakeRedis())


async def test_start_records_pending_state_awaiting_start_date():
    service = _service()

    await service.start(telegram_user_id=42, leave_type_id="lt-1", leave_type_name="Annual Leave")

    state = await service.get_state(42)
    assert state.step == STEP_START_DATE
    assert state.leave_type_id == "lt-1"
    assert await service.is_active(42) is True


async def test_is_active_false_when_nothing_pending():
    service = _service()
    assert await service.is_active(42) is False


async def test_submit_start_date_advances_to_end_date_step():
    service = _service()
    await service.start(telegram_user_id=42, leave_type_id="lt-1", leave_type_name="Annual Leave")

    state = await service.submit_start_date(42, date(2026, 9, 1))

    assert state.step == STEP_END_DATE
    assert state.start_date == "2026-09-01"


async def test_submit_end_date_advances_to_reason_step():
    service = _service()
    await service.start(telegram_user_id=42, leave_type_id="lt-1", leave_type_name="Annual Leave")
    await service.submit_start_date(42, date(2026, 9, 1))

    state = await service.submit_end_date(42, date(2026, 9, 3))

    assert state.step == STEP_REASON
    assert state.end_date == "2026-09-03"


async def test_submit_end_date_raises_when_start_date_step_not_yet_completed():
    service = _service()
    await service.start(telegram_user_id=42, leave_type_id="lt-1", leave_type_name="Annual Leave")

    with pytest.raises(NoLeaveApplicationInProgressError):
        await service.submit_end_date(42, date(2026, 9, 3))


async def test_submit_reason_advances_to_confirm_step():
    service = _service()
    await service.start(telegram_user_id=42, leave_type_id="lt-1", leave_type_name="Annual Leave")
    await service.submit_start_date(42, date(2026, 9, 1))
    await service.submit_end_date(42, date(2026, 9, 3))

    state = await service.submit_reason(42, "Family trip")

    assert state.step == STEP_CONFIRM
    assert state.reason == "Family trip"


async def test_submit_reason_treats_skip_as_no_reason():
    service = _service()
    await service.start(telegram_user_id=42, leave_type_id="lt-1", leave_type_name="Annual Leave")
    await service.submit_start_date(42, date(2026, 9, 1))
    await service.submit_end_date(42, date(2026, 9, 3))

    state = await service.submit_reason(42, "skip")

    assert state.reason is None


async def test_submit_calls_backend_and_clears_state_on_success():
    leave = FakeLeaveEndpoint(apply_result=_APPLIED_REQUEST)
    service = _service(leave=leave)
    await service.start(telegram_user_id=42, leave_type_id="lt-1", leave_type_name="Annual Leave")
    await service.submit_start_date(42, date(2026, 9, 1))
    await service.submit_end_date(42, date(2026, 9, 3))
    await service.submit_reason(42, "skip")

    await service.submit(42)

    assert leave.apply_calls == [
        {
            "telegram_user_id": 42,
            "leave_type_id": "lt-1",
            "start_date": "2026-09-01",
            "end_date": "2026-09-03",
            "reason": None,
        }
    ]
    assert await service.is_active(42) is False


async def test_submit_clears_state_even_when_backend_rejects_it():
    leave = FakeLeaveEndpoint(raise_on_apply=make_hrms_error("insufficient_leave_balance", status_code=422))
    service = _service(leave=leave)
    await service.start(telegram_user_id=42, leave_type_id="lt-1", leave_type_name="Annual Leave")
    await service.submit_start_date(42, date(2026, 9, 1))
    await service.submit_end_date(42, date(2026, 9, 3))
    await service.submit_reason(42, "skip")

    with pytest.raises(Exception) as exc_info:
        await service.submit(42)

    assert exc_info.value.code == "insufficient_leave_balance"
    assert await service.is_active(42) is False  # cleared regardless of outcome — see submit()'s docstring


async def test_submit_without_reaching_confirm_step_raises():
    service = _service()
    await service.start(telegram_user_id=42, leave_type_id="lt-1", leave_type_name="Annual Leave")
    await service.submit_start_date(42, date(2026, 9, 1))

    with pytest.raises(NoLeaveApplicationInProgressError):
        await service.submit(42)


async def test_cancel_clears_pending_state():
    service = _service()
    await service.start(telegram_user_id=42, leave_type_id="lt-1", leave_type_name="Annual Leave")

    await service.cancel(42)

    assert await service.is_active(42) is False


async def test_get_state_returns_none_when_nothing_pending():
    service = _service()
    assert await service.get_state(42) is None
