"""Unit tests for handlers/help_handler.py."""
from __future__ import annotations

from src.auth.account_linking import AccountLinkingService
from src.auth.leave_application import LeaveApplicationService
from src.handlers import help_handler
from src.handlers.context import HandlerContext
from tests.fakes import FakeBotAPIClient, FakeEmployeesEndpoint, FakeLeaveEndpoint, FakeRedis, FakeTelegramUpdate


async def test_help_replies_with_command_list():
    bot = FakeBotAPIClient()
    employees = FakeEmployeesEndpoint()
    leave = FakeLeaveEndpoint()
    ctx = HandlerContext(
        update=FakeTelegramUpdate(text="/help"),
        bot=bot,
        linking=AccountLinkingService(employees, FakeRedis()),
        employees=employees,
        leave=leave,
        leave_application=LeaveApplicationService(leave, FakeRedis()),
    )

    await help_handler.handle_help(ctx)

    assert len(bot.sent_messages) == 1
    text = bot.sent_messages[0]["text"]
    assert "/link" in text
    assert "/profile" in text
    assert "/status" in text
    assert "/unlink" in text
    assert "/apply_leave" in text
    assert "/leave_balance" in text
