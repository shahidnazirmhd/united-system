"""The dependency bundle every handler function receives.

Built once per incoming update by `webhook/update_router.py` and passed by
value to whichever handler the registry dispatches to — this is Dependency
Injection applied at the function-call boundary rather than via a framework
container, appropriate for a service this size (matching the backend's own
preference for explicit composition roots over a DI framework — see
apps/identity/interface/dependencies.py's docstring).

Handlers depend only on this dataclass's attributes, never on `main.py` or
global state — makes each handler trivially unit-testable with a
hand-constructed `HandlerContext` wrapping fakes, the same discipline the
backend's use cases follow with hand-rolled fake repositories.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Every one of these is a dataclass field type only — HandlerContext
    # never constructs any of them (webhook/update_router.py's composition
    # root does that once, at process start). Guarding the imports means
    # this dataclass, and every handler that merely receives a
    # HandlerContext as a parameter, carries no transitive dependency on
    # pydantic/httpx/redis — the whole handlers/ package becomes unit
    # testable with hand-rolled fakes and zero third-party packages
    # installed, mirroring the backend's "domain/application layer has no
    # framework dependency" discipline (HRMS_Architecture.md section 1.2).
    from src.api_client.endpoints.employees import EmployeesEndpoint
    from src.api_client.endpoints.leave import LeaveEndpoint
    from src.auth.account_linking import AccountLinkingService
    from src.auth.leave_application import LeaveApplicationService
    from src.telegram_client.bot_api_client import BotAPIClient
    from src.telegram_client.types import TelegramUpdate


@dataclass
class HandlerContext:
    update: TelegramUpdate
    bot: BotAPIClient
    linking: AccountLinkingService
    employees: EmployeesEndpoint
    leave: LeaveEndpoint
    leave_application: LeaveApplicationService

    # Convenience accessors — every handler needs these, so resolving them
    # once here (rather than every handler re-deriving from `update`) keeps
    # handler bodies focused on their own command's logic.
    @property
    def chat_id(self) -> int:
        assert self.update.chat_id is not None
        return self.update.chat_id

    @property
    def telegram_user_id(self) -> int:
        assert self.update.telegram_user_id is not None
        return self.update.telegram_user_id

    @property
    def telegram_username(self) -> str | None:
        return self.update.telegram_username

    @property
    def command_args(self) -> str:
        """Everything after the first whitespace-separated token of a text
        command, e.g. "/link EMP-000123" -> "EMP-000123". Empty string if
        there's no argument."""
        text = self.update.text or ""
        parts = text.strip().split(maxsplit=1)
        return parts[1].strip() if len(parts) > 1 else ""

    async def reply(self, text: str, *, reply_markup: dict | None = None) -> None:
        await self.bot.send_message(chat_id=self.chat_id, text=text, reply_markup=reply_markup)

    async def edit_message(self, text: str, *, reply_markup: dict | None = None) -> None:
        """Edits the message this update's callback query originated from
        — the "edit existing message" counterpart to `reply()`'s send-new,
        used wherever a callback should update the button UI in place
        (`handlers/calendar_widget.py`'s navigation/cancel, and the flows
        that build on it) rather than leaving a trail of new messages.
        Only valid when handling a callback query with a message attached
        (true for every registered callback in this service) — asserts
        rather than silently falling back to `reply`, so a caller using
        this from the wrong context fails loudly in tests."""
        callback_query = self.update.callback_query
        assert callback_query is not None and callback_query.message is not None
        await self.bot.edit_message_text(
            chat_id=self.chat_id, message_id=callback_query.message.message_id, text=text, reply_markup=reply_markup
        )

    async def answer_callback(self, *, text: str | None = None, show_alert: bool = False) -> None:
        if self.update.callback_query is not None:
            await self.bot.answer_callback_query(
                callback_query_id=self.update.callback_query.id, text=text, show_alert=show_alert
            )
