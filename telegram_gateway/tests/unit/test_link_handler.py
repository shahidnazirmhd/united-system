"""Unit tests for handlers/link_handler.py — registration, OTP submission,
and unlink-with-confirmation."""
from __future__ import annotations

from src.api_client.endpoints.employees import EmployeeProfile, TelegramLinkStatus
from src.auth.account_linking import AccountLinkingService
from src.auth.approval_decision import ApprovalDecisionService
from src.auth.leave_application import LeaveApplicationService
from src.handlers import link_handler
from src.handlers.context import HandlerContext
from tests.fakes import (
    FakeApprovalsEndpoint,
    FakeBotAPIClient,
    FakeCallbackQuery,
    FakeEmployeesEndpoint,
    FakeLeaveEndpoint,
    FakeRedis,
    FakeTelegramUpdate,
    make_hrms_error,
)

_PROFILE = EmployeeProfile(
    id="1", employee_code="E000123", full_name="Ada Lovelace", job_title="Engineer",
    work_email="ada@example.com", phone_number=None, department_name="Engineering", manager_name=None,
    employment_type="full_time", date_of_joining="2024-01-15", status="active",
    current_status="working",
    is_linked_to_telegram=True, telegram_username="ada",
)

_LINKED_STATUS = TelegramLinkStatus(is_linked=True, telegram_username="ada", linked_at="2024-01-01T00:00:00Z")
_UNLINKED_STATUS = TelegramLinkStatus(is_linked=False, telegram_username=None, linked_at=None)


def _context(update, *, employees=None, redis=None) -> HandlerContext:
    employees = employees or FakeEmployeesEndpoint()
    leave = FakeLeaveEndpoint()
    approvals = FakeApprovalsEndpoint()
    return HandlerContext(
        update=update,
        bot=FakeBotAPIClient(),
        linking=AccountLinkingService(employees, redis or FakeRedis()),
        employees=employees,
        leave=leave,
        leave_application=LeaveApplicationService(leave, FakeRedis()),
        approvals=approvals,
        approval_decision=ApprovalDecisionService(approvals, FakeRedis()),
    )


def test_looks_like_otp_accepts_exactly_six_digits():
    assert link_handler.looks_like_otp("123456") is True
    assert link_handler.looks_like_otp(" 123456 ") is True


def test_looks_like_otp_rejects_non_six_digit_text():
    assert link_handler.looks_like_otp("12345") is False
    assert link_handler.looks_like_otp("1234567") is False
    assert link_handler.looks_like_otp("abcdef") is False
    assert link_handler.looks_like_otp(None) is False


async def test_link_without_employee_id_prompts_for_one():
    ctx = _context(FakeTelegramUpdate(text="/link"))

    await link_handler.handle_link(ctx)

    assert "Employee ID" in ctx.bot.sent_messages[0]["text"]


async def test_link_starts_registration_and_asks_for_otp():
    employees = FakeEmployeesEndpoint(link_status=_UNLINKED_STATUS)
    ctx = _context(FakeTelegramUpdate(text="/link E000123"), employees=employees)

    await link_handler.handle_link(ctx)

    assert employees.link_requests[0]["employee_code"] == "E000123"
    assert "6-digit code" in ctx.bot.sent_messages[0]["text"]


async def test_link_shows_friendly_message_for_unknown_employee():
    employees = FakeEmployeesEndpoint(
        link_status=_UNLINKED_STATUS,
        raise_on_request_link=make_hrms_error("employee_not_found", status_code=404),
    )
    ctx = _context(FakeTelegramUpdate(text="/link E999999"), employees=employees)

    await link_handler.handle_link(ctx)

    assert "couldn't find an employee" in ctx.bot.sent_messages[0]["text"]


async def test_link_refuses_when_already_linked():
    employees = FakeEmployeesEndpoint(link_status=_LINKED_STATUS)
    ctx = _context(FakeTelegramUpdate(text="/link E000123"), employees=employees)

    await link_handler.handle_link(ctx)

    assert "already linked" in ctx.bot.sent_messages[0]["text"]


async def test_otp_reply_completes_linking_and_shows_menu():
    employees = FakeEmployeesEndpoint(link_status=_UNLINKED_STATUS, verify_result=_PROFILE)
    ctx = _context(FakeTelegramUpdate(text="123456"), employees=employees)
    await ctx.linking.start_linking(employee_code="E000123", telegram_user_id=42, chat_id=42, telegram_username="ada")

    await link_handler.handle_otp_reply(ctx)

    sent = ctx.bot.sent_messages[-1]
    assert "You're linked" in sent["text"]
    assert "Ada Lovelace" in sent["text"]
    assert sent["reply_markup"] is not None


async def test_otp_reply_shows_friendly_message_for_wrong_code():
    employees = FakeEmployeesEndpoint(
        link_status=_UNLINKED_STATUS,
        raise_on_verify_link=make_hrms_error("invalid_employee_link_otp", status_code=422),
    )
    ctx = _context(FakeTelegramUpdate(text="000000"), employees=employees)
    await ctx.linking.start_linking(employee_code="E000123", telegram_user_id=42, chat_id=42, telegram_username=None)

    await link_handler.handle_otp_reply(ctx)

    assert "check your messages" in ctx.bot.sent_messages[-1]["text"]


async def test_unlink_prompts_confirmation_when_linked():
    employees = FakeEmployeesEndpoint(link_status=_LINKED_STATUS)
    ctx = _context(FakeTelegramUpdate(text="/unlink"), employees=employees)

    await link_handler.handle_unlink(ctx)

    sent = ctx.bot.sent_messages[0]
    assert "Are you sure" in sent["text"]
    assert sent["reply_markup"] is not None


async def test_unlink_does_nothing_when_not_linked():
    employees = FakeEmployeesEndpoint(link_status=_UNLINKED_STATUS)
    ctx = _context(FakeTelegramUpdate(text="/unlink"), employees=employees)

    await link_handler.handle_unlink(ctx)

    assert "isn't linked" in ctx.bot.sent_messages[0]["text"]


async def test_unlink_confirmed_calls_backend():
    employees = FakeEmployeesEndpoint(link_status=_LINKED_STATUS)
    ctx = _context(
        FakeTelegramUpdate(callback_data="account:unlink_confirmed", callback_query=FakeCallbackQuery()),
        employees=employees,
    )

    await link_handler.handle_unlink_confirmed(ctx)

    assert employees.unlink_calls == [42]
    assert "unlinked" in ctx.bot.sent_messages[-1]["text"]


async def test_unlink_cancelled_leaves_session_intact():
    ctx = _context(FakeTelegramUpdate(callback_data="account:unlink_cancelled", callback_query=FakeCallbackQuery()))

    await link_handler.handle_unlink_cancelled(ctx)

    assert "No changes made" in ctx.bot.sent_messages[-1]["text"]


async def test_unlink_prompt_callback_shows_confirmation_when_linked():
    """The "🔓 Unlink account" button on the My Profile card
    (`account:unlink_prompt`) must reach the same confirmation step as the
    /unlink slash command — not skip straight to unlinking."""
    employees = FakeEmployeesEndpoint(link_status=_LINKED_STATUS)
    ctx = _context(
        FakeTelegramUpdate(callback_data="account:unlink_prompt", callback_query=FakeCallbackQuery()),
        employees=employees,
    )

    await link_handler.handle_unlink_prompt_callback(ctx)

    assert len(ctx.bot.answered_callbacks) == 1
    sent = ctx.bot.sent_messages[-1]
    assert "Are you sure" in sent["text"]
    assert sent["reply_markup"] is not None
    assert employees.unlink_calls == []  # confirmation only, backend not called yet


async def test_unlink_prompt_callback_replies_not_linked_when_unlinked():
    employees = FakeEmployeesEndpoint(link_status=_UNLINKED_STATUS)
    ctx = _context(
        FakeTelegramUpdate(callback_data="account:unlink_prompt", callback_query=FakeCallbackQuery()),
        employees=employees,
    )

    await link_handler.handle_unlink_prompt_callback(ctx)

    assert len(ctx.bot.answered_callbacks) == 1
    assert "isn't linked" in ctx.bot.sent_messages[-1]["text"]
