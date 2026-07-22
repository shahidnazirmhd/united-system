"""Reusable Telegram inline calendar date picker — the dispatch half.
`formatting/calendar_keyboard.py` owns the actual keyboard grid and
callback_data encoding; this file owns wiring it into the command registry
(`registry.callback_prefix("cal:")`, per `handlers/registry.py`'s
Open/Closed mechanism — `webhook/update_router.py` needed zero changes to
support this, exactly like Leave's own `leave:apply:type:` prefix) and
resolving a tapped date back to whichever module asked for it.

Any module that needs a "pick a date" step — Leave's start/end date today;
a future Attendance correction date, a Payroll effective date, tomorrow —
registers a `purpose` string once, at import time, via `on_date_selected`,
and calls `start_calendar_flow` to kick one off. This file never imports
any HR module by name; a new consumer is a pure addition here, the same
guarantee `handlers/registry.py`'s command/callback tables already give
every other command.

Navigation (Prev/Next/Today), the month/year picker, and Cancel always edit
the existing calendar message in place, never send a new one — the
"professional, non-spammy" brief `TELEGRAM_GATEWAY.md` describes elsewhere
for every other button in this service applies here too. The initial
display (`start_calendar_flow`) edits the message that carried the button
which started the flow when there is one (e.g. Leave's type-selection
tap), and only falls back to sending a new message when there's nothing to
edit (e.g. a future module that opens a calendar straight from a slash
command).

A purpose's prompt (the message text shown above the grid) can be a plain
string, or an async callable — `Callable[[HandlerContext], Awaitable[str]]`
— resolved fresh on every render. Leave uses this for the end-date
purpose: the prompt shows the already-picked start date each time
("✅ From date: 2026-09-01 ... now pick your To date"), so an employee
navigating months on the end-date calendar never loses track of what
they've already chosen. A plain string is exactly equivalent to an async
callable that always returns that string — most purposes don't need
anything dynamic and can just pass one.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Awaitable, Callable, Union

from src.formatting.calendar_keyboard import (
    ACTION_CANCEL,
    ACTION_DAY,
    ACTION_MONTH_PICK,
    ACTION_MONTH_PICKER_NEXT_YEAR,
    ACTION_MONTH_PICKER_PREV_YEAR,
    ACTION_NEXT,
    ACTION_NOOP,
    ACTION_OPEN_MONTH_PICKER,
    ACTION_PREV,
    ACTION_TODAY,
    MAX_YEAR,
    MIN_YEAR,
    build_calendar_keyboard,
    build_month_picker_keyboard,
    parse_calendar_callback,
    shift_month,
)
from src.handlers.registry import registry
from src.logging_config import log_event

if TYPE_CHECKING:
    from src.handlers.context import HandlerContext

logger = logging.getLogger(__name__)

# Invoked once a date is picked, or with `None` if the picker was
# cancelled — the owning module decides what either outcome means for its
# own conversation state; this widget has no opinion beyond "here's the
# result."
CalendarResultHandler = Callable[["HandlerContext", "date | None"], Awaitable[None]]

# See the module docstring's note on dynamic prompts.
PromptFactory = Callable[["HandlerContext"], Awaitable[str]]
PromptSource = Union[str, PromptFactory]

_EMPTY_KEYBOARD = {"inline_keyboard": []}
_CANCELLED_TEXT = "❌ Cancelled."


@dataclass(frozen=True)
class _CalendarPurpose:
    prompt: PromptSource
    on_result: CalendarResultHandler


_purposes: dict[str, _CalendarPurpose] = {}


def on_date_selected(purpose: str, *, prompt: PromptSource) -> Callable[[CalendarResultHandler], CalendarResultHandler]:
    """Decorator: registers what happens once a date is picked (or
    cancelled) for `purpose`, and the message text shown while that
    purpose's calendar/month-picker is on screen — either a fixed string,
    or an async function of `HandlerContext` resolved fresh every render
    (see module docstring). Call this once, at module import time, exactly
    like `registry.command`/`registry.callback`."""

    def decorator(func: CalendarResultHandler) -> CalendarResultHandler:
        _purposes[purpose] = _CalendarPurpose(prompt=prompt, on_result=func)
        return func

    return decorator


async def _resolve_prompt(prompt: PromptSource, ctx: HandlerContext) -> str:
    if isinstance(prompt, str):
        return prompt
    return await prompt(ctx)


async def start_calendar_flow(ctx: HandlerContext, *, purpose: str, anchor: date | None = None) -> None:
    """Shows the calendar for `purpose` for the first time, defaulting to
    the month containing `anchor` (or today, if not given — e.g. Leave
    anchors the end-date calendar on the just-picked start date, so paging
    isn't needed for the common case of a short leave request)."""
    entry = _purposes[purpose]
    target = anchor or date.today()
    keyboard = build_calendar_keyboard(purpose, target.year, target.month)
    text = await _resolve_prompt(entry.prompt, ctx)

    callback_query = ctx.update.callback_query
    if callback_query is not None and callback_query.message is not None:
        await ctx.edit_message(text, reply_markup=keyboard)
    else:
        await ctx.reply(text, reply_markup=keyboard)


@registry.callback_prefix("cal:")
async def handle_calendar_callback(ctx: HandlerContext) -> None:
    data = ctx.update.callback_data or ""
    parsed = parse_calendar_callback(data)
    if parsed is None or parsed.purpose not in _purposes:
        # Defensive only: malformed/stale callback_data, or a purpose that
        # was registered by a module no longer in this build — every
        # purpose reachable by a real employee is registered at import
        # time.
        log_event(logger, logging.INFO, "calendar_callback_unrecognized", data=data)
        await ctx.answer_callback(text="This action is no longer available.")
        return

    entry = _purposes[parsed.purpose]

    if parsed.action == ACTION_NOOP:
        await ctx.answer_callback()
        return

    if parsed.action in (ACTION_PREV, ACTION_NEXT):
        await ctx.answer_callback()
        new_year, new_month = shift_month(parsed.year, parsed.month, -1 if parsed.action == ACTION_PREV else 1)
        if not (MIN_YEAR <= new_year <= MAX_YEAR):
            # Reached the picker's supported range — ignore rather than
            # paging into a nonsensical year (see calendar_keyboard.py's
            # MIN_YEAR/MAX_YEAR docstring).
            return
        keyboard = build_calendar_keyboard(parsed.purpose, new_year, new_month)
        await ctx.edit_message(await _resolve_prompt(entry.prompt, ctx), reply_markup=keyboard)
        return

    if parsed.action == ACTION_OPEN_MONTH_PICKER:
        await ctx.answer_callback()
        keyboard = build_month_picker_keyboard(parsed.purpose, parsed.year)
        await ctx.edit_message(await _resolve_prompt(entry.prompt, ctx), reply_markup=keyboard)
        return

    if parsed.action in (ACTION_MONTH_PICKER_PREV_YEAR, ACTION_MONTH_PICKER_NEXT_YEAR):
        await ctx.answer_callback()
        new_year = parsed.year + (-1 if parsed.action == ACTION_MONTH_PICKER_PREV_YEAR else 1)
        if not (MIN_YEAR <= new_year <= MAX_YEAR):
            return
        keyboard = build_month_picker_keyboard(parsed.purpose, new_year)
        await ctx.edit_message(await _resolve_prompt(entry.prompt, ctx), reply_markup=keyboard)
        return

    if parsed.action == ACTION_MONTH_PICK:
        await ctx.answer_callback()
        keyboard = build_calendar_keyboard(parsed.purpose, parsed.year, parsed.month)
        await ctx.edit_message(await _resolve_prompt(entry.prompt, ctx), reply_markup=keyboard)
        return

    if parsed.action == ACTION_CANCEL:
        await ctx.answer_callback(text="Cancelled.")
        await ctx.edit_message(_CANCELLED_TEXT, reply_markup=_EMPTY_KEYBOARD)
        await entry.on_result(ctx, None)
        return

    if parsed.action == ACTION_TODAY:
        await ctx.answer_callback()
        await entry.on_result(ctx, date.today())
        return

    if parsed.action == ACTION_DAY and parsed.day is not None:
        try:
            selected = date(parsed.year, parsed.month, parsed.day)
        except ValueError:
            # Should be unreachable — build_calendar_keyboard only ever
            # emits real day numbers for the month it built — but the
            # callback_data is still user-controlled input, so this stays
            # defensive rather than trusting it.
            await ctx.answer_callback(text="That's not a valid date.")
            return
        await ctx.answer_callback()
        await entry.on_result(ctx, selected)
        return

    await ctx.answer_callback()
