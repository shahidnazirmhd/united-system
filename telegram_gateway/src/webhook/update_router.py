"""Inspects a parsed Telegram Update and dispatches to the correct handler.

Per HRMS_Folder_Structure.md section 3.1: "this router is the Gateway's
*only* piece of branching logic, and it branches purely on 'which handler,'
never on business rules." Every branch below answers only "which handler
function runs," nothing else — no HR data is read or interpreted here.

Deliberately never edited to add a new command: see handlers/registry.py's
docstring for the Open/Closed mechanism this router relies on.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from src.errors import GatewayError, friendly_message_for
from src.handlers import approval_handlers, leave_handlers, link_handler
from src.handlers.context import HandlerContext
from src.handlers.registry import CommandRegistry
from src.logging_config import log_event

if TYPE_CHECKING:
    # `route()` only receives an already-parsed TelegramUpdate as a
    # parameter (webhook/server.py does the real pydantic parsing) — never
    # constructs one itself, so this doesn't need to be a real import here.
    from src.telegram_client.types import TelegramUpdate

logger = logging.getLogger(__name__)

_UNKNOWN_COMMAND_REPLY = "I didn't understand that. Type /help to see what I can do."


class Dependencies:
    """Groups everything `update_router.route` needs beyond the update
    itself and the registry — constructed once at process start
    (main.py) and passed through, never re-created per request."""

    __slots__ = (
        "bot",
        "linking",
        "employees",
        "leave",
        "leave_application",
        "approvals",
        "approval_decision",
    )

    def __init__(
        self, *, bot, linking, employees, leave, leave_application, approvals, approval_decision
    ) -> None:
        self.bot = bot
        self.linking = linking
        self.employees = employees
        self.leave = leave
        self.leave_application = leave_application
        self.approvals = approvals
        self.approval_decision = approval_decision


async def route(update: TelegramUpdate, deps: Dependencies, registry: CommandRegistry) -> None:
    if update.chat_id is None or update.telegram_user_id is None:
        # An update kind this service doesn't model (edited message, inline
        # query, etc. — see TelegramUpdate's docstring). Deliberately a
        # silent no-op, not an error: Telegram sends many update kinds no
        # bot handles, and 200-acknowledging all of them is expected.
        return

    ctx = HandlerContext(
        update=update,
        bot=deps.bot,
        linking=deps.linking,
        employees=deps.employees,
        leave=deps.leave,
        leave_application=deps.leave_application,
        approvals=deps.approvals,
        approval_decision=deps.approval_decision,
    )

    log_event(
        logger,
        logging.INFO,
        "update_received",
        telegram_user_id=ctx.telegram_user_id,
        chat_id=ctx.chat_id,
        kind="callback_query" if update.callback_query is not None else "message",
    )

    try:
        if update.callback_query is not None:
            await _route_callback(ctx, registry)
        elif update.message is not None:
            await _route_message(ctx, registry)
    except GatewayError as exc:
        # A handler that let a GatewayError escape rather than catching it
        # locally (most do catch, for a more specific message — this is the
        # safety net for the ones that don't need to distinguish).
        log_event(logger, logging.WARNING, "handler_gateway_error", telegram_user_id=ctx.telegram_user_id, error=str(exc))
        await ctx.reply(friendly_message_for(exc))
    except Exception:
        # Never leak a stack trace into a chat message — matches
        # shared_kernel/api/exception_handler.py's discipline on the
        # backend side exactly: the client (here, the employee) sees a
        # generic message, the real detail goes to logs only.
        log_event(logger, logging.ERROR, "handler_unexpected_error", telegram_user_id=ctx.telegram_user_id, exc_info=True)
        logger.exception("Unhandled exception while routing update")
        await ctx.reply("Something went wrong on our end. Please try again in a moment.")


async def _route_callback(ctx: HandlerContext, registry: CommandRegistry) -> None:
    data = ctx.update.callback_data
    handler = registry.get_callback(data) if data else None
    if handler is None:
        log_event(logger, logging.INFO, "unknown_callback", telegram_user_id=ctx.telegram_user_id, data=data)
        await ctx.answer_callback(text="This action is no longer available.")
        return
    await handler.func(ctx)


async def _route_message(ctx: HandlerContext, registry: CommandRegistry) -> None:
    text = (ctx.update.text or "").strip()
    if not text:
        return

    if text.startswith("/"):
        command_name = text[1:].split()[0].split("@")[0].lower()
        handler = registry.get_command(command_name)
        if handler is not None:
            await handler.func(ctx)
            return
        await ctx.reply(_UNKNOWN_COMMAND_REPLY)
        return

    menu_handler = registry.get_command_by_menu_label(text)
    if menu_handler is not None:
        await menu_handler.func(ctx)
        return

    if link_handler.looks_like_otp(text) and await ctx.linking.is_awaiting_otp(ctx.telegram_user_id):
        await link_handler.handle_otp_reply(ctx)
        return

    # Apply Leave's multi-step conversation (start date -> end date ->
    # reason) is free text at every step, unlike the OTP flow's fixed
    # 6-digit shape — checked after OTP (linking always takes priority; an
    # employee mid-link has no leave conversation to be mid-way through
    # anyway) and before falling through to "unknown command."
    if await ctx.leave_application.is_active(ctx.telegram_user_id):
        await leave_handlers.handle_apply_leave_free_text(ctx)
        return

    # Approval Engine (Phase 9) — the optional-comment step following an
    # Approve/Reject tap is likewise free text at every point, checked last
    # (after OTP and Apply Leave, both of which take priority for the same
    # reason Apply Leave already yields to OTP: a chat can only meaningfully
    # be mid-way through one conversation at a time, and this is checked
    # last simply because it was added last).
    if await ctx.approval_decision.is_active(ctx.telegram_user_id):
        await approval_handlers.handle_approval_comment_free_text(ctx)
        return

    await ctx.reply(_UNKNOWN_COMMAND_REPLY)
