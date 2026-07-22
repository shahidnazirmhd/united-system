"""Unit tests for handlers/profile_handler.py."""
from __future__ import annotations

import pytest

from src.api_client.endpoints.employees import EmployeeProfile
from src.auth.account_linking import AccountLinkingService
from src.auth.leave_application import LeaveApplicationService
from src.errors import TelegramAPIError
from src.handlers import profile_handler
from src.handlers.context import HandlerContext
from tests.fakes import (
    FakeBotAPIClient,
    FakeCallbackMessage,
    FakeCallbackQuery,
    FakeEmployeesEndpoint,
    FakeLeaveEndpoint,
    FakeRedis,
    FakeTelegramUpdate,
    make_hrms_error,
)

_PROFILE = EmployeeProfile(
    id="1", employee_code="EMP-000123", full_name="Ada Lovelace", job_title="Engineer",
    work_email="ada@example.com", phone_number=None, department_name="Engineering", manager_name=None,
    employment_type="full_time", date_of_joining="2024-01-15", status="active",
    is_linked_to_telegram=True, telegram_username="ada",
)


def _build_context(update, employees, *, bot=None) -> HandlerContext:
    leave = FakeLeaveEndpoint()
    return HandlerContext(
        update=update,
        bot=bot or FakeBotAPIClient(),
        linking=AccountLinkingService(employees, FakeRedis()),
        employees=employees,
        leave=leave,
        leave_application=LeaveApplicationService(leave, FakeRedis()),
    )


async def test_profile_shows_friendly_message_when_not_linked():
    error = make_hrms_error("employee_not_linked_to_telegram", status_code=404)
    ctx = _build_context(FakeTelegramUpdate(text="/profile"), FakeEmployeesEndpoint(raise_on_get_profile=error))

    await profile_handler.handle_profile(ctx)

    assert "/link" in ctx.bot.sent_messages[0]["text"]


async def test_profile_shows_formatted_card_when_linked():
    ctx = _build_context(FakeTelegramUpdate(text="/profile"), FakeEmployeesEndpoint(profile=_PROFILE))

    await profile_handler.handle_profile(ctx)

    sent = ctx.bot.sent_messages[0]
    assert "Ada Lovelace" in sent["text"]
    assert sent["reply_markup"] is not None


async def test_profile_shows_friendly_message_on_backend_error():
    error = make_hrms_error("employee_not_found", status_code=404)
    ctx = _build_context(FakeTelegramUpdate(text="/profile"), FakeEmployeesEndpoint(raise_on_get_profile=error))

    await profile_handler.handle_profile(ctx)

    assert "couldn't find an employee" in ctx.bot.sent_messages[0]["text"]


async def test_profile_refresh_callback_edits_the_existing_message():
    update = FakeTelegramUpdate(
        callback_data="profile:refresh", callback_query=FakeCallbackQuery(id="cb-1", message=FakeCallbackMessage(message_id=99))
    )
    ctx = _build_context(update, FakeEmployeesEndpoint(profile=_PROFILE))

    await profile_handler.handle_profile_refresh(ctx)

    assert len(ctx.bot.answered_callbacks) == 1
    assert len(ctx.bot.edited_messages) == 1
    assert ctx.bot.edited_messages[0]["message_id"] == 99
    assert "Ada Lovelace" in ctx.bot.edited_messages[0]["text"]


async def test_profile_refresh_swallows_message_not_modified_error():
    """Regression test: tapping Refresh when the card's content hasn't
    changed used to bubble a TelegramAPIError ("message is not modified")
    all the way up to update_router's generic "Something went wrong"
    reply, even though nothing was actually wrong. The callback should
    still be answered (so the button's spinner stops) and the handler
    should complete without raising or sending any error message."""
    bot = FakeBotAPIClient(
        raise_on_edit_message=TelegramAPIError(
            "Telegram editMessageText failed: Bad Request: message is not modified",
            description="Bad Request: message is not modified",
        )
    )
    update = FakeTelegramUpdate(
        callback_data="profile:refresh", callback_query=FakeCallbackQuery(id="cb-1", message=FakeCallbackMessage(message_id=99))
    )
    ctx = _build_context(update, FakeEmployeesEndpoint(profile=_PROFILE), bot=bot)

    await profile_handler.handle_profile_refresh(ctx)

    assert len(ctx.bot.answered_callbacks) == 1
    assert ctx.bot.edited_messages == []
    assert ctx.bot.sent_messages == []


async def test_profile_refresh_reraises_genuine_telegram_errors():
    """A real Telegram failure (as opposed to the harmless "not modified"
    case above) must still surface — update_router's top-level handler is
    what turns it into a "Something went wrong" reply."""
    bot = FakeBotAPIClient(
        raise_on_edit_message=TelegramAPIError("Telegram editMessageText failed: chat not found", description="chat not found")
    )
    update = FakeTelegramUpdate(
        callback_data="profile:refresh", callback_query=FakeCallbackQuery(id="cb-1", message=FakeCallbackMessage(message_id=99))
    )
    ctx = _build_context(update, FakeEmployeesEndpoint(profile=_PROFILE), bot=bot)

    with pytest.raises(TelegramAPIError):
        await profile_handler.handle_profile_refresh(ctx)
