"""Unit tests for auth/account_linking.py's AccountLinkingService — the
two-step registration flow (employee code -> OTP -> linked).

Employee & Telegram Authentication refactor: there is no token pair to
save/refresh anymore — completing linking just clears the local "awaiting
OTP" flag and hands back the now-linked EmployeeProfile. "Is linked" is
answered fresh from the backend every time (FakeEmployeesEndpoint.
link_status), never cached locally.
"""
from __future__ import annotations

import pytest

from src.api_client.endpoints.employees import EmployeeProfile, TelegramLinkStatus
from src.auth.account_linking import AccountLinkingService
from src.errors import LinkingInProgressConflictError, NoLinkingInProgressError
from tests.fakes import FakeEmployeesEndpoint, FakeRedis, make_hrms_error

_PROFILE = EmployeeProfile(
    id="1", employee_code="EMP-000123", full_name="Ada Lovelace", job_title="Engineer",
    work_email="ada@example.com", phone_number=None, department_name="Engineering", manager_name=None,
    employment_type="full_time", date_of_joining="2024-01-15", status="active",
    is_linked_to_telegram=True, telegram_username="ada",
)


def _service(employees=None, redis=None) -> AccountLinkingService:
    return AccountLinkingService(employees or FakeEmployeesEndpoint(), redis or FakeRedis())


async def test_start_linking_calls_backend_and_records_pending_state():
    employees = FakeEmployeesEndpoint()
    redis = FakeRedis()
    service = _service(employees=employees, redis=redis)

    await service.start_linking(
        employee_code="EMP-000123", telegram_user_id=42, chat_id=42, telegram_username="ada"
    )

    assert employees.link_requests == [
        {"employee_code": "EMP-000123", "telegram_user_id": 42, "chat_id": 42, "telegram_username": "ada"}
    ]
    assert await service.is_awaiting_otp(42) is True


async def test_start_linking_propagates_backend_errors_unmodified():
    employees = FakeEmployeesEndpoint(raise_on_request_link=make_hrms_error("employee_not_found", status_code=404))
    service = _service(employees=employees)

    with pytest.raises(Exception) as exc_info:
        await service.start_linking(employee_code="EMP-999999", telegram_user_id=42, chat_id=42, telegram_username=None)

    assert exc_info.value.code == "employee_not_found"
    assert await service.is_awaiting_otp(42) is False  # a failed request must not leave stale pending state


async def test_start_linking_rejects_a_second_concurrent_attempt():
    service = _service()
    await service.start_linking(employee_code="EMP-000123", telegram_user_id=42, chat_id=42, telegram_username=None)

    with pytest.raises(LinkingInProgressConflictError):
        await service.start_linking(employee_code="EMP-000123", telegram_user_id=42, chat_id=42, telegram_username=None)


async def test_complete_linking_without_a_pending_request_raises():
    service = _service()

    with pytest.raises(NoLinkingInProgressError):
        await service.complete_linking(telegram_user_id=42, chat_id=42, otp="123456", telegram_username=None)


async def test_complete_linking_returns_profile_and_clears_pending_state_on_success():
    employees = FakeEmployeesEndpoint(verify_result=_PROFILE)
    service = _service(employees=employees)
    await service.start_linking(employee_code="EMP-000123", telegram_user_id=42, chat_id=42, telegram_username=None)

    result = await service.complete_linking(telegram_user_id=42, chat_id=42, otp="123456", telegram_username="ada")

    assert result.full_name == "Ada Lovelace"
    assert await service.is_awaiting_otp(42) is False


async def test_complete_linking_leaves_pending_state_on_wrong_otp_so_the_employee_can_retry():
    employees = FakeEmployeesEndpoint(raise_on_verify_link=make_hrms_error("invalid_employee_link_otp", status_code=422))
    service = _service(employees=employees)
    await service.start_linking(employee_code="EMP-000123", telegram_user_id=42, chat_id=42, telegram_username=None)

    with pytest.raises(Exception) as exc_info:
        await service.complete_linking(telegram_user_id=42, chat_id=42, otp="000000", telegram_username=None)

    assert exc_info.value.code == "invalid_employee_link_otp"
    assert await service.is_awaiting_otp(42) is True  # still pending — the employee can just retype the code


async def test_complete_linking_clears_pending_state_on_too_many_attempts_so_link_works_immediately():
    # Unlike a plain wrong-OTP rejection, too_many_otp_attempts means the
    # backend has permanently locked that specific token — leaving our own
    # "awaiting OTP" flag set would make the very next /link bounce off
    # LinkingInProgressConflictError for up to another 10 minutes, telling
    # the employee to "wait" for something that's already dead.
    employees = FakeEmployeesEndpoint(
        raise_on_verify_link=make_hrms_error("too_many_otp_attempts", status_code=422)
    )
    service = _service(employees=employees)
    await service.start_linking(employee_code="EMP-000123", telegram_user_id=42, chat_id=42, telegram_username=None)

    with pytest.raises(Exception) as exc_info:
        await service.complete_linking(telegram_user_id=42, chat_id=42, otp="000000", telegram_username=None)

    assert exc_info.value.code == "too_many_otp_attempts"
    assert await service.is_awaiting_otp(42) is False  # cleared — /link works right away, no stale wait


async def test_unlink_calls_backend_and_clears_pending_state():
    employees = FakeEmployeesEndpoint()
    service = _service(employees=employees)
    await service.start_linking(employee_code="EMP-000123", telegram_user_id=42, chat_id=42, telegram_username=None)

    await service.unlink(telegram_user_id=42)

    assert employees.unlink_calls == [42]
    assert await service.is_awaiting_otp(42) is False


async def test_is_linked_reflects_backend_status():
    employees = FakeEmployeesEndpoint(link_status=TelegramLinkStatus(is_linked=False, telegram_username=None, linked_at=None))
    service = _service(employees=employees)
    assert await service.is_linked(42) is False

    employees.link_status = TelegramLinkStatus(is_linked=True, telegram_username="ada", linked_at="2024-01-01T00:00:00Z")
    assert await service.is_linked(42) is True
