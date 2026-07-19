"""Unit tests for handlers/status_handler.py."""
from __future__ import annotations

from src.api_client.endpoints.employees import EmployeeProfile
from src.auth.account_linking import AccountLinkingService
from src.handlers import status_handler
from src.handlers.context import HandlerContext
from tests.fakes import FakeBotAPIClient, FakeEmployeesEndpoint, FakeRedis, FakeTelegramUpdate, make_hrms_error

_PROFILE = EmployeeProfile(
    id="1", employee_code="EMP-000123", full_name="Ada Lovelace", job_title="Engineer",
    work_email="ada@example.com", phone_number=None, department_name="Engineering", manager_name=None,
    employment_type="full_time", date_of_joining="2024-01-15", status="suspended",
    is_linked_to_telegram=True, telegram_username="ada",
)


async def test_status_shows_concise_status_when_linked():
    employees = FakeEmployeesEndpoint(profile=_PROFILE)
    ctx = HandlerContext(
        update=FakeTelegramUpdate(text="/status"),
        bot=FakeBotAPIClient(),
        linking=AccountLinkingService(employees, FakeRedis()),
        employees=employees,
    )

    await status_handler.handle_status(ctx)

    text = ctx.bot.sent_messages[0]["text"]
    assert "🔴 Suspended" in text


async def test_status_prompts_to_link_when_not_linked():
    error = make_hrms_error("employee_not_linked_to_telegram", status_code=404)
    employees = FakeEmployeesEndpoint(raise_on_get_profile=error)
    ctx = HandlerContext(
        update=FakeTelegramUpdate(text="/status"),
        bot=FakeBotAPIClient(),
        linking=AccountLinkingService(employees, FakeRedis()),
        employees=employees,
    )

    await status_handler.handle_status(ctx)

    assert "/link" in ctx.bot.sent_messages[0]["text"]
