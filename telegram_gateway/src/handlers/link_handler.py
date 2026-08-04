"""Registration/link flow (Employee ID -> OTP -> linked -> auto sign-in)
and account unlinking — the Phase 7 brief's core self-service flow.

`handle_link` and `handle_otp_reply` are the only two entry points that
touch `auth/account_linking.py`; both are thin — parse input, call the
service, format the result — with all the actual state/flow logic living in
`AccountLinkingService` (see that file's docstring), not here.

`handle_otp_reply` is deliberately NOT `@registry.command(...)` — a submitted
OTP is plain free-text (Telegram gives no way to slash-command a 6-digit
reply), so `webhook/update_router.py` routes to it directly based on
`AccountLinkingService.is_awaiting_otp`, not through the command table.
"""
from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from src.errors import GatewayError, friendly_message_for
from src.formatting.keyboards import build_main_menu_keyboard, build_unlink_confirmation_keyboard, remove_keyboard
from src.handlers.registry import registry
from src.logging_config import log_event

if TYPE_CHECKING:
    from src.api_client.endpoints.employees import EmployeeProfile
    from src.handlers.context import HandlerContext

logger = logging.getLogger(__name__)

_OTP_PATTERN = re.compile(r"^\d{6}$")


@registry.command("link")
async def handle_link(ctx: HandlerContext) -> None:
    employee_code = ctx.command_args
    if not employee_code:
        await ctx.reply(
            "Please include your Employee ID, e.g. `/link E000123`."
        )
        return

    if await ctx.linking.is_linked(ctx.telegram_user_id):
        await ctx.reply(
            "Your Telegram account is already linked. Send /unlink first if you want to link a different account."
        )
        return

    try:
        await ctx.linking.start_linking(
            employee_code=employee_code,
            telegram_user_id=ctx.telegram_user_id,
            chat_id=ctx.chat_id,
            telegram_username=ctx.telegram_username,
        )
    except GatewayError as exc:
        log_event(logger, logging.INFO, "link_request_failed", telegram_user_id=ctx.telegram_user_id, error=str(exc))
        await ctx.reply(friendly_message_for(exc))
        return

    await ctx.reply(
        "✅ We've sent a one-time code. Please reply with the 6-digit code to finish linking your account."
    )


def looks_like_otp(text: str | None) -> bool:
    """Used by update_router to decide whether an incoming free-text
    message should be routed here rather than treated as an unknown
    command — deliberately a narrow shape check (exactly 6 digits), not
    "any text while awaiting-otp," so a stray message doesn't get silently
    swallowed as a wrong OTP attempt."""
    return text is not None and bool(_OTP_PATTERN.match(text.strip()))


async def handle_otp_reply(ctx: HandlerContext) -> None:
    otp = (ctx.update.text or "").strip()
    try:
        profile: EmployeeProfile = await ctx.linking.complete_linking(
            telegram_user_id=ctx.telegram_user_id,
            chat_id=ctx.chat_id,
            otp=otp,
            telegram_username=ctx.telegram_username,
        )
    except GatewayError as exc:
        log_event(logger, logging.INFO, "link_verify_failed", telegram_user_id=ctx.telegram_user_id, error=str(exc))
        await ctx.reply(friendly_message_for(exc))
        return

    await ctx.reply(
        f"🎉 You're linked, {profile.full_name}! Use the menu below to get started.",
        reply_markup=build_main_menu_keyboard(registry),
    )


async def _prompt_unlink(ctx: HandlerContext) -> None:
    """Shared by the `/unlink` slash command and the "🔓 Unlink account"
    button on the "My Profile" card (`account:unlink_prompt` callback below)
    — both are just different ways to reach the same confirmation step, so
    there's exactly one place that decides what that step looks like."""
    if not await ctx.linking.is_linked(ctx.telegram_user_id):
        await ctx.reply("Your Telegram account isn't linked to anything right now.")
        return
    await ctx.reply(
        "Are you sure you want to unlink your Telegram account? You'll need to link again to use this bot.",
        reply_markup=build_unlink_confirmation_keyboard(),
    )


@registry.command("unlink")
async def handle_unlink(ctx: HandlerContext) -> None:
    await _prompt_unlink(ctx)


@registry.callback("account:unlink_prompt")
async def handle_unlink_prompt_callback(ctx: HandlerContext) -> None:
    """The profile card's "🔓 Unlink account" button. Deliberately routes
    through the same confirmation step `/unlink` does, rather than the
    button's callback_data pointing straight at `account:unlink_confirmed`
    — skipping confirmation from a single tap would be too easy to hit by
    accident."""
    await ctx.answer_callback()
    await _prompt_unlink(ctx)


@registry.callback("account:unlink_confirmed")
async def handle_unlink_confirmed(ctx: HandlerContext) -> None:
    await ctx.answer_callback()
    try:
        await ctx.linking.unlink(telegram_user_id=ctx.telegram_user_id)
    except GatewayError as exc:
        log_event(logger, logging.INFO, "unlink_failed", telegram_user_id=ctx.telegram_user_id, error=str(exc))
        await ctx.reply(friendly_message_for(exc))
        return
    await ctx.reply("🔓 Your Telegram account has been unlinked.", reply_markup=remove_keyboard())


@registry.callback("account:unlink_cancelled")
async def handle_unlink_cancelled(ctx: HandlerContext) -> None:
    await ctx.answer_callback(text="Cancelled.")
    await ctx.reply("No changes made — you're still linked.", reply_markup=build_main_menu_keyboard(registry))
