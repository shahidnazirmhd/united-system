"""Leave commands — "one file per command family" per
HRMS_Folder_Structure.md section 3.5, matching `handlers/link_handler.py`'s
precedent (which houses both /link and /unlink) by housing every Leave
command and callback here: balance, types, apply (multi-step), history,
detail, cancel.

Every handler does exactly three things — deserialize the update, call
`ctx.leave`/`ctx.leave_application`, format and send the result — with all
actual state/flow logic living in `auth/leave_application.py` (for the
multi-step Apply Leave conversation) or nowhere at all (the other commands
are simple request/response, no conversation needed). No business rule
(balance sufficiency, overlap, date validity) is decided here — every one
of those is the backend's job; this file only ever reacts to whatever
`HRMSAPIError` the backend raises, via `errors.friendly_message_for`, the
same discipline `handlers/link_handler.py` already established.

Start/end date entry is `handlers/calendar_widget.py`'s generic inline
calendar (see PURPOSE_START_DATE/PURPOSE_END_DATE below and
`TELEGRAM_GATEWAY.md` §3b) — this file only supplies the two "what happens
once a date is picked" callbacks, never any calendar UI/grid logic itself.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import TYPE_CHECKING

from src.auth.leave_application import STEP_CONFIRM, STEP_END_DATE, STEP_REASON, STEP_START_DATE
from src.errors import GatewayError, friendly_message_for
from src.formatting.keyboards import (
    build_apply_leave_confirm_keyboard,
    build_cancel_leave_confirm_keyboard,
    build_leave_request_selection_keyboard,
    build_leave_type_selection_keyboard,
)
from src.formatting.leave_formatter import (
    format_apply_leave_confirmation,
    format_apply_leave_prompt_end_date,
    format_apply_leave_prompt_reason,
    format_apply_leave_prompt_start_date,
    format_cancel_leave_confirm_prompt,
    format_cancel_leave_prompt,
    format_leave_applied,
    format_leave_balances,
    format_leave_cancelled,
    format_leave_history,
    format_leave_request_detail,
    format_leave_types_prompt,
    format_no_cancellable_requests,
)
from src.handlers import calendar_widget
from src.handlers.registry import registry
from src.logging_config import log_event

if TYPE_CHECKING:
    from src.handlers.context import HandlerContext

logger = logging.getLogger(__name__)

# Calendar purposes for the two date steps of Apply Leave — see
# handlers/calendar_widget.py's docstring. Dot-separated, never colons
# (colons are calendar_keyboard.py's own callback_data field separator).
PURPOSE_START_DATE = "leave.apply.start"
PURPOSE_END_DATE = "leave.apply.end"

# Requests still worth offering a "cancel" button for — mirrors the
# backend's own allowed-from states for LeaveRequestService.cancel_leave
# (domain/entities.py LeaveRequest.cancel: PENDING or APPROVED). Purely a
# display filter (which rows get a button), not a re-implementation of the
# actual cancellation rule — the backend enforces that rule for real when
# the button is tapped, this only decides which rows are worth showing.
_CANCELLABLE_STATUSES = {"pending", "approved"}

_HISTORY_PAGE_SIZE = 5


# ============================================================================
# Leave Types
# ============================================================================


@registry.command("leave_types")
async def handle_leave_types(ctx: HandlerContext) -> None:
    try:
        leave_types = await ctx.leave.list_types()
    except GatewayError as exc:
        log_event(logger, logging.INFO, "leave_types_failed", telegram_user_id=ctx.telegram_user_id, error=str(exc))
        await ctx.reply(friendly_message_for(exc))
        return

    if not leave_types:
        await ctx.reply("No leave types are configured yet. Please contact HR.")
        return

    lines = [f"• *{lt.name}* (`{lt.code}`) — {lt.default_annual_days} days/year" for lt in leave_types]
    await ctx.reply("*Leave Types*\n\n" + "\n".join(lines))


# ============================================================================
# Leave Balance
# ============================================================================


@registry.command("leave_balance", menu_label="💰 Leave Balance", menu_order=30)
async def handle_leave_balance(ctx: HandlerContext) -> None:
    try:
        balances = await ctx.leave.get_balances(telegram_user_id=ctx.telegram_user_id)
    except GatewayError as exc:
        log_event(logger, logging.INFO, "leave_balance_failed", telegram_user_id=ctx.telegram_user_id, error=str(exc))
        await ctx.reply(friendly_message_for(exc))
        return
    await ctx.reply(format_leave_balances(balances))


# ============================================================================
# Apply Leave (multi-step)
# ============================================================================


@registry.command("apply_leave", menu_label="📝 Apply Leave", menu_order=31)
async def handle_apply_leave_start(ctx: HandlerContext) -> None:
    try:
        leave_types = await ctx.leave.list_types()
    except GatewayError as exc:
        log_event(logger, logging.INFO, "apply_leave_start_failed", telegram_user_id=ctx.telegram_user_id, error=str(exc))
        await ctx.reply(friendly_message_for(exc))
        return

    if not leave_types:
        await ctx.reply("No leave types are configured yet. Please contact HR.")
        return

    await ctx.reply(format_leave_types_prompt(), reply_markup=build_leave_type_selection_keyboard(leave_types))


@registry.callback_prefix("leave:apply:type:")
async def handle_apply_leave_type_selected(ctx: HandlerContext) -> None:
    await ctx.answer_callback()
    data = ctx.update.callback_data or ""
    leave_type_id = data.removeprefix("leave:apply:type:")

    # Look up the human-readable name for the confirmation summary later —
    # re-fetches rather than trusting the button's own label text, so a
    # leave type renamed between listing and tapping still shows correctly.
    try:
        leave_types = await ctx.leave.list_types()
    except GatewayError as exc:
        await ctx.reply(friendly_message_for(exc))
        return
    selected = next((lt for lt in leave_types if lt.id == leave_type_id), None)
    if selected is None:
        await ctx.reply("That leave type is no longer available. Send /apply_leave to try again.")
        return

    await ctx.leave_application.start(
        telegram_user_id=ctx.telegram_user_id, leave_type_id=selected.id, leave_type_name=selected.name
    )
    await calendar_widget.start_calendar_flow(ctx, purpose=PURPOSE_START_DATE)


@registry.callback("leave:apply:abort")
async def handle_apply_leave_abort(ctx: HandlerContext) -> None:
    await ctx.answer_callback(text="Cancelled.")
    await ctx.leave_application.cancel(ctx.telegram_user_id)
    await ctx.reply("No leave application was submitted.")


async def _end_date_prompt(ctx: HandlerContext) -> str:
    """The end-date calendar's prompt is dynamic, not a fixed string —
    resolved fresh every time that calendar (or its month/year picker) is
    rendered, so it always echoes back whatever From date is actually in
    the conversation's state right now, however many times the employee
    pages around before tapping a day. See calendar_widget.py's
    PromptFactory."""
    state = await ctx.leave_application.get_state(ctx.telegram_user_id)
    from_date = state.start_date if state is not None else None
    return format_apply_leave_prompt_end_date(from_date=from_date)


@calendar_widget.on_date_selected(PURPOSE_START_DATE, prompt=format_apply_leave_prompt_start_date())
async def _handle_start_date_picked(ctx: HandlerContext, value: date | None) -> None:
    """Invoked by handlers/calendar_widget.py once a start date is picked
    (or the picker cancelled — `value` is None). Never called for free
    text; that's the point of moving date entry to a calendar."""
    if value is None:
        await ctx.leave_application.cancel(ctx.telegram_user_id)
        return
    try:
        await ctx.leave_application.submit_start_date(ctx.telegram_user_id, value)
    except GatewayError as exc:
        log_event(logger, logging.INFO, "apply_leave_step_failed", telegram_user_id=ctx.telegram_user_id, error=str(exc))
        await ctx.reply(friendly_message_for(exc))
        return
    # Anchor the end-date calendar on the just-picked start date, not
    # today — most leave requests span a few nearby days, so this avoids
    # making the employee page the calendar forward again immediately.
    await calendar_widget.start_calendar_flow(ctx, purpose=PURPOSE_END_DATE, anchor=value)


@calendar_widget.on_date_selected(PURPOSE_END_DATE, prompt=_end_date_prompt)
async def _handle_end_date_picked(ctx: HandlerContext, value: date | None) -> None:
    if value is None:
        await ctx.leave_application.cancel(ctx.telegram_user_id)
        return
    try:
        new_state = await ctx.leave_application.submit_end_date(ctx.telegram_user_id, value)
    except GatewayError as exc:
        log_event(logger, logging.INFO, "apply_leave_step_failed", telegram_user_id=ctx.telegram_user_id, error=str(exc))
        await ctx.reply(friendly_message_for(exc))
        return
    # Reason is still free text — clear the calendar's buttons rather than
    # leaving them on screen once they no longer do anything useful, and
    # recap both picked dates so the employee can see they registered
    # correctly before typing anything else.
    await ctx.edit_message(
        format_apply_leave_prompt_reason(from_date=new_state.start_date, to_date=new_state.end_date),
        reply_markup={"inline_keyboard": []},
    )


async def handle_apply_leave_free_text(ctx: HandlerContext) -> None:
    """Routed here by `webhook/update_router.py` when a plain-text message
    arrives while `ctx.leave_application.is_active()` is true — the
    Apply Leave equivalent of `link_handler.handle_otp_reply`. Dispatches
    on the conversation's current step. Only STEP_REASON is actually
    free-text input; STEP_START_DATE/STEP_END_DATE are calendar-only (see
    the on_date_selected handlers above) — free text arriving during
    either of those just nudges toward the buttons, the same "nudge, don't
    silently ignore" treatment STEP_CONFIRM already gets below."""
    text = (ctx.update.text or "").strip()
    state = await ctx.leave_application.get_state(ctx.telegram_user_id)
    if state is None:
        # Should be unreachable — update_router only routes here when
        # is_active() is true — but defensive rather than assuming.
        await ctx.reply("I wasn't expecting that. Send /apply_leave to start a new leave application.")
        return

    if state.step in (STEP_START_DATE, STEP_END_DATE):
        await ctx.reply("Please use the calendar buttons above to pick a date.")
        return

    try:
        if state.step == STEP_REASON:
            new_state = await ctx.leave_application.submit_reason(ctx.telegram_user_id, text)
            await ctx.reply(
                format_apply_leave_confirmation(new_state), reply_markup=build_apply_leave_confirm_keyboard()
            )
            return
    except GatewayError as exc:
        log_event(logger, logging.INFO, "apply_leave_step_failed", telegram_user_id=ctx.telegram_user_id, error=str(exc))
        await ctx.reply(friendly_message_for(exc))
        return

    # state.step == STEP_CONFIRM and the employee typed free text instead of
    # tapping a button — nudge them toward the buttons rather than silently
    # ignoring the message.
    if state.step == STEP_CONFIRM:
        await ctx.reply(
            format_apply_leave_confirmation(state), reply_markup=build_apply_leave_confirm_keyboard()
        )


@registry.callback("leave:apply:confirm")
async def handle_apply_leave_confirm(ctx: HandlerContext) -> None:
    await ctx.answer_callback()
    try:
        result = await ctx.leave_application.submit(ctx.telegram_user_id)
    except GatewayError as exc:
        log_event(logger, logging.INFO, "apply_leave_submit_failed", telegram_user_id=ctx.telegram_user_id, error=str(exc))
        await ctx.reply(friendly_message_for(exc))
        return
    await ctx.reply(format_leave_applied(result))


# ============================================================================
# Leave History / Detail
# ============================================================================


@registry.command("leave_history", menu_label="📜 Leave History", menu_order=32)
async def handle_leave_history(ctx: HandlerContext) -> None:
    page = 1
    raw_page = ctx.command_args.strip()
    if raw_page.isdigit():
        page = max(1, int(raw_page))

    try:
        result = await ctx.leave.get_history(telegram_user_id=ctx.telegram_user_id, page=page, page_size=_HISTORY_PAGE_SIZE)
    except GatewayError as exc:
        log_event(logger, logging.INFO, "leave_history_failed", telegram_user_id=ctx.telegram_user_id, error=str(exc))
        await ctx.reply(friendly_message_for(exc))
        return
    await ctx.reply(format_leave_history(result))


@registry.command("leave_request")
async def handle_leave_request_detail(ctx: HandlerContext) -> None:
    """/leave_request <id> — View Leave Request Details. No menu button
    (an id isn't something an employee has memorized); reachable via
    /leave_history's listed ids, or /help."""
    leave_request_id = ctx.command_args.strip()
    if not leave_request_id:
        await ctx.reply("Please include a leave request ID, e.g. `/leave_request 018f...` — see /leave_history.")
        return

    try:
        result = await ctx.leave.get_detail(telegram_user_id=ctx.telegram_user_id, leave_request_id=leave_request_id)
    except GatewayError as exc:
        log_event(logger, logging.INFO, "leave_detail_failed", telegram_user_id=ctx.telegram_user_id, error=str(exc))
        await ctx.reply(friendly_message_for(exc))
        return
    await ctx.reply(format_leave_request_detail(result))


# ============================================================================
# Cancel Leave Request
# ============================================================================


@registry.command("cancel_leave", menu_label="🚫 Cancel Leave", menu_order=33)
async def handle_cancel_leave_start(ctx: HandlerContext) -> None:
    try:
        result = await ctx.leave.get_history(telegram_user_id=ctx.telegram_user_id, page=1, page_size=50)
    except GatewayError as exc:
        log_event(logger, logging.INFO, "cancel_leave_start_failed", telegram_user_id=ctx.telegram_user_id, error=str(exc))
        await ctx.reply(friendly_message_for(exc))
        return

    cancellable = [r for r in result.items if r.status in _CANCELLABLE_STATUSES]
    if not cancellable:
        await ctx.reply(format_no_cancellable_requests())
        return

    await ctx.reply(format_cancel_leave_prompt(), reply_markup=build_leave_request_selection_keyboard(cancellable))


@registry.callback_prefix("leave:cancel:select:")
async def handle_cancel_leave_selected(ctx: HandlerContext) -> None:
    await ctx.answer_callback()
    data = ctx.update.callback_data or ""
    leave_request_id = data.removeprefix("leave:cancel:select:")

    try:
        request = await ctx.leave.get_detail(telegram_user_id=ctx.telegram_user_id, leave_request_id=leave_request_id)
    except GatewayError as exc:
        await ctx.reply(friendly_message_for(exc))
        return

    await ctx.reply(
        format_cancel_leave_confirm_prompt(request), reply_markup=build_cancel_leave_confirm_keyboard(request.id)
    )


@registry.callback_prefix("leave:cancel:confirm:")
async def handle_cancel_leave_confirmed(ctx: HandlerContext) -> None:
    await ctx.answer_callback()
    data = ctx.update.callback_data or ""
    leave_request_id = data.removeprefix("leave:cancel:confirm:")

    try:
        result = await ctx.leave.cancel(
            telegram_user_id=ctx.telegram_user_id, leave_request_id=leave_request_id, cancellation_reason=None
        )
    except GatewayError as exc:
        log_event(logger, logging.INFO, "cancel_leave_confirm_failed", telegram_user_id=ctx.telegram_user_id, error=str(exc))
        await ctx.reply(friendly_message_for(exc))
        return
    await ctx.reply(format_leave_cancelled(result))


@registry.callback("leave:cancel:abort")
async def handle_cancel_leave_aborted(ctx: HandlerContext) -> None:
    await ctx.answer_callback(text="Cancelled.")
    await ctx.reply("No changes made.")
