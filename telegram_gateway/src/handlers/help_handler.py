"""/help — a static command list. No backend call, no business logic; this
is the one handler that's pure presentation, matching
HRMS_Folder_Structure.md section 3.5's "no handler makes any decision the
backend hasn't already made" — there's simply no decision to make here.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from src.handlers.registry import registry

if TYPE_CHECKING:
    from src.handlers.context import HandlerContext

_HELP_TEXT = (
    "*United HRMS Bot — Commands*\n\n"
    "/link `<employee_id>` — Link your Telegram account to your employee record\n"
    "/profile — View your profile\n"
    "/status — View your current employment status\n"
    "/unlink — Unlink your Telegram account\n"
    "/help — Show this message\n\n"
    "You can also use the menu buttons below instead of typing commands."
)


@registry.command("help", menu_label="❓ Help", menu_order=90)
async def handle_help(ctx: HandlerContext) -> None:
    await ctx.reply(_HELP_TEXT)
