"""Approval Engine commands/callbacks — "one file per command family" per
HRMS_Folder_Structure.md section 3.5, matching `handlers/leave_handlers.py`'s
precedent.

Two ways a manager reaches a decision screen:
  1. An unsolicited push notification (`webhook/server.py`'s
     `POST /internal/notify` route builds the message directly, using
     `build_approval_decision_keyboard`/`format_approval_requested_push` —
     it does not go through this file's command dispatch at all, since
     there is no incoming Telegram update to route for a push).
  2. `/pending_approvals` — a fallback for a manager who wants to see
     everything currently waiting on them (e.g. they missed/dismissed a
     push, or are catching up after being away) — this file's own command.

From either path, tapping Approve/Reject always leads to the same optional-
comment mini-flow (`auth/approval_decision.py`), mirroring
`handlers/leave_handlers.py`'s reason-entry step: type a comment, or send
"skip".

No business rule (must be the assigned approver, must currently be
pending, ...) is decided here — every one of those is the backend's job;
this file only ever reacts to whatever `HRMSAPIError` the backend raises,
via `errors.friendly_message_for`.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from src.auth.approval_decision import DECISION_APPROVE, DECISION_REJECT
from src.errors import GatewayError, friendly_message_for
from src.formatting.approval_formatter import (
    format_approval_comment_prompt,
    format_approval_decision_result,
    format_no_pending_approvals,
    format_pending_approval_item,
)
from src.formatting.keyboards import build_approval_decision_keyboard
from src.handlers.registry import registry
from src.logging_config import log_event

if TYPE_CHECKING:
    from src.handlers.context import HandlerContext

logger = logging.getLogger(__name__)

_CALLBACK_PREFIX_APPROVE = "approval:decide:approve:"
_CALLBACK_PREFIX_REJECT = "approval:decide:reject:"


@registry.command("pending_approvals", menu_label="✅ Pending Approvals", menu_order=40)
async def handle_pending_approvals(ctx: HandlerContext) -> None:
    try:
        pending = await ctx.approvals.list_pending(telegram_user_id=ctx.telegram_user_id)
    except GatewayError as exc:
        log_event(logger, logging.INFO, "pending_approvals_failed", telegram_user_id=ctx.telegram_user_id, error=str(exc))
        await ctx.reply(friendly_message_for(exc))
        return

    if not pending:
        await ctx.reply(format_no_pending_approvals())
        return

    # One message per pending approval, each carrying its own Approve/
    # Reject buttons — an approval request needs two independent actions
    # (unlike Leave's single-select lists), so it cannot be collapsed into
    # one shared keyboard the way /leave_history's rows are.
    for approval_request in pending:
        await ctx.reply(
            format_pending_approval_item(approval_request),
            reply_markup=build_approval_decision_keyboard(approval_request.id),
        )


async def _handle_decision_tapped(ctx: HandlerContext, *, decision: str, prefix: str) -> None:
    await ctx.answer_callback()
    # Strip this message's buttons immediately — a decision must not be
    # submittable twice from the same stale tap (same reasoning as every
    # other "clear before proceeding" callback in handlers/leave_handlers.py).
    await ctx.clear_reply_markup()
    data = ctx.update.callback_data or ""
    approval_request_id = data.removeprefix(prefix)

    await ctx.approval_decision.start(
        telegram_user_id=ctx.telegram_user_id, approval_request_id=approval_request_id, decision=decision
    )
    await ctx.reply(format_approval_comment_prompt(decision))


@registry.callback_prefix(_CALLBACK_PREFIX_APPROVE)
async def handle_approve_tapped(ctx: HandlerContext) -> None:
    await _handle_decision_tapped(ctx, decision=DECISION_APPROVE, prefix=_CALLBACK_PREFIX_APPROVE)


@registry.callback_prefix(_CALLBACK_PREFIX_REJECT)
async def handle_reject_tapped(ctx: HandlerContext) -> None:
    await _handle_decision_tapped(ctx, decision=DECISION_REJECT, prefix=_CALLBACK_PREFIX_REJECT)


async def handle_approval_comment_free_text(ctx: HandlerContext) -> None:
    """Routed here by `webhook/update_router.py` when a plain-text message
    arrives while `ctx.approval_decision.is_active()` is true — the
    Approvals equivalent of `leave_handlers.handle_apply_leave_free_text`."""
    text = (ctx.update.text or "").strip()
    try:
        result = await ctx.approval_decision.submit_comment(ctx.telegram_user_id, text)
    except GatewayError as exc:
        log_event(
            logger, logging.INFO, "approval_decision_submit_failed", telegram_user_id=ctx.telegram_user_id, error=str(exc)
        )
        await ctx.reply(friendly_message_for(exc))
        return
    await ctx.reply(format_approval_decision_result(result))
