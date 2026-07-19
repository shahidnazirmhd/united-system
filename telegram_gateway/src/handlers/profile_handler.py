""""My Profile" — the Phase 7 brief's self-service profile card.

Does exactly what a DRF viewset action does (HRMS_Folder_Structure.md
section 3.5): call the one endpoint it's allowed to call
(`api_client/endpoints/employees.py`, identified by the caller's Telegram
user id — no session to resolve, see auth/account_linking.py), hand the
result to `formatting/`, and send it. No field is computed, transformed, or
decided here beyond what the formatter already encapsulates.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from src.errors import GatewayError, friendly_message_for
from src.formatting.keyboards import build_profile_actions_keyboard
from src.formatting.profile_formatter import format_my_profile
from src.handlers.registry import registry
from src.logging_config import log_event

if TYPE_CHECKING:
    from src.handlers.context import HandlerContext

logger = logging.getLogger(__name__)


async def _render_profile(ctx: HandlerContext) -> tuple[str, dict]:
    profile = await ctx.employees.get_profile(telegram_user_id=ctx.telegram_user_id)
    return format_my_profile(profile), build_profile_actions_keyboard()


@registry.command("profile", menu_label="👤 My Profile", menu_order=10)
async def handle_profile(ctx: HandlerContext) -> None:
    try:
        text, keyboard = await _render_profile(ctx)
    except GatewayError as exc:
        log_event(logger, logging.INFO, "profile_view_failed", telegram_user_id=ctx.telegram_user_id, error=str(exc))
        await ctx.reply(friendly_message_for(exc))
        return
    await ctx.reply(text, reply_markup=keyboard)


@registry.callback("profile:refresh")
async def handle_profile_refresh(ctx: HandlerContext) -> None:
    await ctx.answer_callback()
    try:
        text, keyboard = await _render_profile(ctx)
    except GatewayError as exc:
        await ctx.answer_callback(text=friendly_message_for(exc), show_alert=True)
        return

    callback_query = ctx.update.callback_query
    if callback_query is not None and callback_query.message is not None:
        await ctx.bot.edit_message_text(
            chat_id=ctx.chat_id, message_id=callback_query.message.message_id, text=text, reply_markup=keyboard
        )
