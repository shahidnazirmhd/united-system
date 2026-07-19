"""/start — Telegram's own convention for a bot's first message in a chat.

No `menu_label`: per registry.py's docstring, /start only makes sense once,
not as a recurring menu button. Branches purely on "already linked or not"
to decide the greeting — even that is not a business decision, just a
routing one (which of two static messages to show), so this stays
consistent with "no business logic in handlers."
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from src.formatting.keyboards import build_main_menu_keyboard
from src.handlers.registry import registry

if TYPE_CHECKING:
    from src.handlers.context import HandlerContext

_WELCOME_LINKED = (
    "👋 Welcome back! Use the menu below, or type /help to see available commands."
)
_WELCOME_UNLINKED = (
    "👋 Welcome to the United HRMS Bot!\n\n"
    "To get started, link your Telegram account to your employee record:\n"
    "Send `/link <your employee ID>` — for example: `/link EMP-000123`\n\n"
    "Your HR team can provide your employee ID if you don't have it handy."
)


@registry.command("start")
async def handle_start(ctx: HandlerContext) -> None:
    if await ctx.linking.is_linked(ctx.telegram_user_id):
        await ctx.reply(_WELCOME_LINKED, reply_markup=build_main_menu_keyboard(registry))
    else:
        await ctx.reply(_WELCOME_UNLINKED)
