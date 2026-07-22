"""Unit tests for webhook/update_router.py — the "which handler runs"
dispatch logic, exercised end-to-end through `route()` rather than by
calling individual handlers directly."""
from __future__ import annotations

from src.api_client.endpoints.employees import EmployeeProfile, TelegramLinkStatus
from src.auth.account_linking import AccountLinkingService
from src.auth.leave_application import LeaveApplicationService
from src.handlers import (  # noqa: F401 — registers commands
    help_handler,
    leave_handlers,
    link_handler,
    profile_handler,
    start_handler,
    status_handler,
)
from src.handlers.registry import registry
from src.webhook.update_router import Dependencies, route
from tests.fakes import (
    FakeBotAPIClient,
    FakeCallbackQuery,
    FakeEmployeesEndpoint,
    FakeLeaveEndpoint,
    FakeRedis,
    FakeTelegramUpdate,
)

_PROFILE = EmployeeProfile(
    id="1", employee_code="EMP-000123", full_name="Ada Lovelace", job_title="Engineer",
    work_email="ada@example.com", phone_number=None, department_name="Engineering", manager_name=None,
    employment_type="full_time", date_of_joining="2024-01-15", status="active",
    is_linked_to_telegram=True, telegram_username="ada",
)
_LINKED_STATUS = TelegramLinkStatus(is_linked=True, telegram_username="ada", linked_at="2024-01-01T00:00:00Z")
_UNLINKED_STATUS = TelegramLinkStatus(is_linked=False, telegram_username=None, linked_at=None)


def _deps(*, employees=None, leave=None):
    employees = employees or FakeEmployeesEndpoint(link_status=_UNLINKED_STATUS)
    leave = leave or FakeLeaveEndpoint()
    bot = FakeBotAPIClient()
    deps = Dependencies(
        bot=bot,
        linking=AccountLinkingService(employees, FakeRedis()),
        employees=employees,
        leave=leave,
        leave_application=LeaveApplicationService(leave, FakeRedis()),
    )
    return deps, bot


async def test_slash_command_dispatches_to_registered_handler():
    deps, bot = _deps()

    await route(FakeTelegramUpdate(text="/help"), deps, registry)

    assert "/link" in bot.sent_messages[0]["text"]


async def test_unknown_slash_command_gets_generic_reply():
    deps, bot = _deps()

    await route(FakeTelegramUpdate(text="/nonexistent"), deps, registry)

    assert "didn't understand" in bot.sent_messages[0]["text"]


async def test_menu_button_label_text_dispatches_same_as_slash_command():
    deps, bot = _deps()

    await route(FakeTelegramUpdate(text="❓ Help"), deps, registry)

    assert "/link" in bot.sent_messages[0]["text"]


async def test_six_digit_text_routes_to_otp_handler_only_when_linking_pending():
    deps, bot = _deps()

    await route(FakeTelegramUpdate(text="123456"), deps, registry)

    # No /link was ever started, so this must NOT be swallowed as an OTP
    # attempt — it should fall through to the generic "unknown" reply.
    assert "didn't understand" in bot.sent_messages[0]["text"]


async def test_six_digit_text_completes_linking_when_awaited():
    employees = FakeEmployeesEndpoint(link_status=_UNLINKED_STATUS, verify_result=_PROFILE)
    deps, bot = _deps(employees=employees)
    await deps.linking.start_linking(employee_code="EMP-000123", telegram_user_id=42, chat_id=42, telegram_username=None)

    await route(FakeTelegramUpdate(text="123456"), deps, registry)

    assert "You're linked" in bot.sent_messages[-1]["text"]


async def test_callback_query_dispatches_to_registered_callback():
    deps, bot = _deps()

    await route(
        FakeTelegramUpdate(callback_data="account:unlink_cancelled", callback_query=FakeCallbackQuery()), deps, registry
    )

    assert "No changes made" in bot.sent_messages[-1]["text"]


async def test_unlink_prompt_callback_from_profile_card_dispatches_correctly():
    """Regression test for the profile card's "🔓 Unlink account" button:
    its callback_data (account:unlink_prompt) must actually be registered
    and reachable through the real router, not just through calling the
    handler function directly."""
    employees = FakeEmployeesEndpoint(link_status=_LINKED_STATUS)
    deps, bot = _deps(employees=employees)

    await route(
        FakeTelegramUpdate(callback_data="account:unlink_prompt", callback_query=FakeCallbackQuery()), deps, registry
    )

    assert "Are you sure" in bot.sent_messages[-1]["text"]


async def test_unknown_callback_answers_gracefully_without_crashing():
    deps, bot = _deps()

    await route(
        FakeTelegramUpdate(callback_data="some:unregistered_callback", callback_query=FakeCallbackQuery()), deps, registry
    )

    assert len(bot.answered_callbacks) == 1
    assert "no longer available" in bot.answered_callbacks[0]["text"]


async def test_update_with_no_chat_id_is_a_silent_no_op():
    deps, bot = _deps()

    await route(FakeTelegramUpdate(chat_id=None, telegram_user_id=None, text="/help"), deps, registry)

    assert bot.sent_messages == []


async def test_unexpected_exception_in_a_handler_never_leaks_a_stack_trace():
    class ExplodingEmployeesEndpoint:
        async def get_profile(self, *, telegram_user_id):
            raise RuntimeError("boom — some unexpected bug")

    deps, bot = _deps(employees=ExplodingEmployeesEndpoint())

    await route(FakeTelegramUpdate(text="/profile"), deps, registry)

    sent_text = bot.sent_messages[-1]["text"]
    assert "boom" not in sent_text
    assert "went wrong" in sent_text
