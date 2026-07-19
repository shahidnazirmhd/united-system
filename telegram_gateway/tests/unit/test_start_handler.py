"""Unit tests for handlers/start_handler.py."""
from __future__ import annotations

from src.api_client.endpoints.employees import TelegramLinkStatus
from src.auth.account_linking import AccountLinkingService
from src.handlers import start_handler
from src.handlers.context import HandlerContext
from tests.fakes import FakeBotAPIClient, FakeEmployeesEndpoint, FakeRedis, FakeTelegramUpdate


async def test_start_shows_onboarding_message_when_unlinked():
    bot = FakeBotAPIClient()
    employees = FakeEmployeesEndpoint(
        link_status=TelegramLinkStatus(is_linked=False, telegram_username=None, linked_at=None)
    )
    ctx = HandlerContext(
        update=FakeTelegramUpdate(text="/start"),
        bot=bot,
        linking=AccountLinkingService(employees, FakeRedis()),
        employees=employees,
    )

    await start_handler.handle_start(ctx)

    assert len(bot.sent_messages) == 1
    assert "/link" in bot.sent_messages[0]["text"]
    assert bot.sent_messages[0]["reply_markup"] is None


async def test_start_shows_menu_when_already_linked():
    bot = FakeBotAPIClient()
    employees = FakeEmployeesEndpoint(
        link_status=TelegramLinkStatus(is_linked=True, telegram_username="ada", linked_at="2024-01-01T00:00:00Z")
    )
    ctx = HandlerContext(
        update=FakeTelegramUpdate(text="/start"),
        bot=bot,
        linking=AccountLinkingService(employees, FakeRedis()),
        employees=employees,
    )

    await start_handler.handle_start(ctx)

    assert len(bot.sent_messages) == 1
    assert "Welcome back" in bot.sent_messages[0]["text"]
    assert bot.sent_messages[0]["reply_markup"] is not None
