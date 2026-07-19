"""Unit tests for handlers/help_handler.py."""
from __future__ import annotations

from src.auth.account_linking import AccountLinkingService
from src.handlers import help_handler
from src.handlers.context import HandlerContext
from tests.fakes import FakeBotAPIClient, FakeEmployeesEndpoint, FakeRedis, FakeTelegramUpdate


async def test_help_replies_with_command_list():
    bot = FakeBotAPIClient()
    employees = FakeEmployeesEndpoint()
    ctx = HandlerContext(
        update=FakeTelegramUpdate(text="/help"),
        bot=bot,
        linking=AccountLinkingService(employees, FakeRedis()),
        employees=employees,
    )

    await help_handler.handle_help(ctx)

    assert len(bot.sent_messages) == 1
    text = bot.sent_messages[0]["text"]
    assert "/link" in text
    assert "/profile" in text
    assert "/status" in text
    assert "/unlink" in text
