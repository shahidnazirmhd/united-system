"""Unit tests for handlers/calendar_widget.py — the generic dispatch layer
wiring formatting/calendar_keyboard.py's pure grid into the command
registry and resolving a tapped date back to whichever purpose asked for
it. Registers its own throwaway test purposes (`_TEST_PURPOSE`) rather than
relying on Leave's real ones, so this file stays a true test of the
generic widget, independent of any one HR module.
"""
from __future__ import annotations

from datetime import date

from src.auth.account_linking import AccountLinkingService
from src.auth.leave_application import LeaveApplicationService
from src.handlers import calendar_widget
from src.handlers.context import HandlerContext
from src.formatting.calendar_keyboard import MAX_YEAR, MIN_YEAR
from tests.fakes import (
    FakeBotAPIClient,
    FakeCallbackMessage,
    FakeCallbackQuery,
    FakeEmployeesEndpoint,
    FakeLeaveEndpoint,
    FakeRedis,
    FakeTelegramUpdate,
)

_TEST_PURPOSE = "test.widget.purpose"
_TEST_PROMPT = "Pick a test date:"
_DYNAMIC_PURPOSE = "test.widget.dynamic"

_results: list[tuple[HandlerContext, "date | None"]] = []
_dynamic_prompt_text = "initial dynamic prompt"


@calendar_widget.on_date_selected(_TEST_PURPOSE, prompt=_TEST_PROMPT)
async def _record_result(ctx: HandlerContext, value: "date | None") -> None:
    _results.append((ctx, value))


async def _dynamic_prompt(ctx: HandlerContext) -> str:
    return _dynamic_prompt_text


@calendar_widget.on_date_selected(_DYNAMIC_PURPOSE, prompt=_dynamic_prompt)
async def _record_dynamic_result(ctx: HandlerContext, value: "date | None") -> None:
    _results.append((ctx, value))


def _ctx(update) -> HandlerContext:
    employees = FakeEmployeesEndpoint()
    leave = FakeLeaveEndpoint()
    return HandlerContext(
        update=update,
        bot=FakeBotAPIClient(),
        linking=AccountLinkingService(employees, FakeRedis()),
        employees=employees,
        leave=leave,
        leave_application=LeaveApplicationService(leave, FakeRedis()),
    )


def _reset():
    _results.clear()


# --- start_calendar_flow ----------------------------------------------


async def test_start_calendar_flow_edits_existing_message_when_reached_via_callback():
    _reset()
    ctx = _ctx(FakeTelegramUpdate(callback_data="whatever", callback_query=FakeCallbackQuery(message=FakeCallbackMessage(message_id=7))))

    await calendar_widget.start_calendar_flow(ctx, purpose=_TEST_PURPOSE, anchor=date(2026, 9, 1))

    assert ctx.bot.sent_messages == []
    assert len(ctx.bot.edited_messages) == 1
    edited = ctx.bot.edited_messages[0]
    assert edited["message_id"] == 7
    assert edited["text"] == _TEST_PROMPT
    assert edited["reply_markup"]["inline_keyboard"]


async def test_start_calendar_flow_sends_new_message_when_no_callback_to_edit():
    _reset()
    ctx = _ctx(FakeTelegramUpdate(text="/whatever"))

    await calendar_widget.start_calendar_flow(ctx, purpose=_TEST_PURPOSE, anchor=date(2026, 9, 1))

    assert ctx.bot.edited_messages == []
    assert len(ctx.bot.sent_messages) == 1
    assert ctx.bot.sent_messages[0]["text"] == _TEST_PROMPT


async def test_start_calendar_flow_defaults_to_todays_month_with_no_anchor():
    _reset()
    ctx = _ctx(FakeTelegramUpdate(text="/whatever"))

    await calendar_widget.start_calendar_flow(ctx, purpose=_TEST_PURPOSE)

    today = date.today()
    keyboard = ctx.bot.sent_messages[0]["reply_markup"]
    # Today's own day button should be present and visually marked.
    labels = [b["text"] for row in keyboard["inline_keyboard"] for b in row]
    assert f"•{today.day}•" in labels


# --- handle_calendar_callback: noop -------------------------------------


async def test_noop_button_is_a_pure_no_op():
    _reset()
    ctx = _ctx(
        FakeTelegramUpdate(
            callback_data=f"cal:{_TEST_PURPOSE}:noop:202609", callback_query=FakeCallbackQuery(message=FakeCallbackMessage(message_id=7))
        )
    )

    await calendar_widget.handle_calendar_callback(ctx)

    assert len(ctx.bot.answered_callbacks) == 1
    assert ctx.bot.edited_messages == []
    assert ctx.bot.sent_messages == []
    assert _results == []


# --- handle_calendar_callback: navigation -------------------------------


async def test_prev_navigation_edits_message_with_shifted_month_and_same_prompt():
    _reset()
    ctx = _ctx(
        FakeTelegramUpdate(
            callback_data=f"cal:{_TEST_PURPOSE}:prev:202609", callback_query=FakeCallbackQuery(message=FakeCallbackMessage(message_id=7))
        )
    )

    await calendar_widget.handle_calendar_callback(ctx)

    assert len(ctx.bot.answered_callbacks) == 1
    assert len(ctx.bot.edited_messages) == 1
    edited = ctx.bot.edited_messages[0]
    assert edited["text"] == _TEST_PROMPT
    labels = [b["text"] for row in edited["reply_markup"]["inline_keyboard"] for b in row]
    assert "August 2026" in labels
    assert _results == []  # navigation never resolves the picker


async def test_next_navigation_edits_message_with_shifted_month():
    _reset()
    ctx = _ctx(
        FakeTelegramUpdate(
            callback_data=f"cal:{_TEST_PURPOSE}:next:202609", callback_query=FakeCallbackQuery(message=FakeCallbackMessage(message_id=7))
        )
    )

    await calendar_widget.handle_calendar_callback(ctx)

    edited = ctx.bot.edited_messages[0]
    labels = [b["text"] for row in edited["reply_markup"]["inline_keyboard"] for b in row]
    assert "October 2026" in labels


async def test_navigation_stops_at_min_year():
    _reset()
    ctx = _ctx(
        FakeTelegramUpdate(
            callback_data=f"cal:{_TEST_PURPOSE}:prev:{MIN_YEAR:04d}01",
            callback_query=FakeCallbackQuery(message=FakeCallbackMessage(message_id=7)),
        )
    )

    await calendar_widget.handle_calendar_callback(ctx)

    assert len(ctx.bot.answered_callbacks) == 1  # still acknowledges the tap
    assert ctx.bot.edited_messages == []  # but doesn't page any further back


async def test_navigation_stops_at_max_year():
    _reset()
    ctx = _ctx(
        FakeTelegramUpdate(
            callback_data=f"cal:{_TEST_PURPOSE}:next:{MAX_YEAR:04d}12",
            callback_query=FakeCallbackQuery(message=FakeCallbackMessage(message_id=7)),
        )
    )

    await calendar_widget.handle_calendar_callback(ctx)

    assert ctx.bot.edited_messages == []


# --- handle_calendar_callback: today ------------------------------------


async def test_today_button_resolves_the_picker_with_todays_date():
    _reset()
    ctx = _ctx(
        FakeTelegramUpdate(
            callback_data=f"cal:{_TEST_PURPOSE}:today:202609", callback_query=FakeCallbackQuery(message=FakeCallbackMessage(message_id=7))
        )
    )

    await calendar_widget.handle_calendar_callback(ctx)

    assert len(ctx.bot.answered_callbacks) == 1
    assert len(_results) == 1
    assert _results[0][1] == date.today()


# --- handle_calendar_callback: day selection -----------------------------


async def test_day_button_resolves_the_picker_with_the_tapped_date():
    _reset()
    ctx = _ctx(
        FakeTelegramUpdate(
            callback_data=f"cal:{_TEST_PURPOSE}:day:202609:15",
            callback_query=FakeCallbackQuery(message=FakeCallbackMessage(message_id=7)),
        )
    )

    await calendar_widget.handle_calendar_callback(ctx)

    assert len(_results) == 1
    assert _results[0][1] == date(2026, 9, 15)


# --- handle_calendar_callback: cancel -------------------------------------


async def test_cancel_button_edits_message_clears_keyboard_and_resolves_with_none():
    _reset()
    ctx = _ctx(
        FakeTelegramUpdate(
            callback_data=f"cal:{_TEST_PURPOSE}:cancel:202609", callback_query=FakeCallbackQuery(message=FakeCallbackMessage(message_id=7))
        )
    )

    await calendar_widget.handle_calendar_callback(ctx)

    assert len(ctx.bot.answered_callbacks) == 1
    edited = ctx.bot.edited_messages[0]
    assert "Cancelled" in edited["text"]
    assert edited["reply_markup"] == {"inline_keyboard": []}
    assert len(_results) == 1
    assert _results[0][1] is None


# --- handle_calendar_callback: unrecognized -------------------------------


async def test_malformed_callback_data_is_handled_gracefully():
    _reset()
    ctx = _ctx(
        FakeTelegramUpdate(callback_data="cal:not-valid", callback_query=FakeCallbackQuery(message=FakeCallbackMessage(message_id=7)))
    )

    await calendar_widget.handle_calendar_callback(ctx)

    assert len(ctx.bot.answered_callbacks) == 1
    assert "no longer available" in ctx.bot.answered_callbacks[0]["text"]
    assert ctx.bot.edited_messages == []
    assert _results == []


async def test_unregistered_purpose_is_handled_gracefully():
    _reset()
    ctx = _ctx(
        FakeTelegramUpdate(
            callback_data="cal:nobody.registered.this:today:202609",
            callback_query=FakeCallbackQuery(message=FakeCallbackMessage(message_id=7)),
        )
    )

    await calendar_widget.handle_calendar_callback(ctx)

    assert "no longer available" in ctx.bot.answered_callbacks[0]["text"]
    assert _results == []


# --- handle_calendar_callback: month/year picker --------------------------


async def test_opening_the_month_picker_edits_message_with_year_and_month_buttons():
    _reset()
    ctx = _ctx(
        FakeTelegramUpdate(
            callback_data=f"cal:{_TEST_PURPOSE}:open_month:202609",
            callback_query=FakeCallbackQuery(message=FakeCallbackMessage(message_id=7)),
        )
    )

    await calendar_widget.handle_calendar_callback(ctx)

    assert len(ctx.bot.answered_callbacks) == 1
    edited = ctx.bot.edited_messages[0]
    assert edited["text"] == _TEST_PROMPT
    labels = [b["text"] for row in edited["reply_markup"]["inline_keyboard"] for b in row]
    assert "2026" in labels
    assert "Sep" in labels
    assert _results == []  # opening the picker never resolves the flow


async def test_month_picker_prev_year_edits_message_with_shifted_year():
    _reset()
    ctx = _ctx(
        FakeTelegramUpdate(
            callback_data=f"cal:{_TEST_PURPOSE}:month_prev_year:202601",
            callback_query=FakeCallbackQuery(message=FakeCallbackMessage(message_id=7)),
        )
    )

    await calendar_widget.handle_calendar_callback(ctx)

    labels = [b["text"] for row in ctx.bot.edited_messages[0]["reply_markup"]["inline_keyboard"] for b in row]
    assert "2025" in labels


async def test_month_picker_next_year_edits_message_with_shifted_year():
    _reset()
    ctx = _ctx(
        FakeTelegramUpdate(
            callback_data=f"cal:{_TEST_PURPOSE}:month_next_year:202601",
            callback_query=FakeCallbackQuery(message=FakeCallbackMessage(message_id=7)),
        )
    )

    await calendar_widget.handle_calendar_callback(ctx)

    labels = [b["text"] for row in ctx.bot.edited_messages[0]["reply_markup"]["inline_keyboard"] for b in row]
    assert "2027" in labels


async def test_month_picker_year_navigation_stops_at_min_and_max_year():
    _reset()
    ctx = _ctx(
        FakeTelegramUpdate(
            callback_data=f"cal:{_TEST_PURPOSE}:month_prev_year:{MIN_YEAR:04d}01",
            callback_query=FakeCallbackQuery(message=FakeCallbackMessage(message_id=7)),
        )
    )
    await calendar_widget.handle_calendar_callback(ctx)
    assert ctx.bot.edited_messages == []

    ctx = _ctx(
        FakeTelegramUpdate(
            callback_data=f"cal:{_TEST_PURPOSE}:month_next_year:{MAX_YEAR:04d}01",
            callback_query=FakeCallbackQuery(message=FakeCallbackMessage(message_id=7)),
        )
    )
    await calendar_widget.handle_calendar_callback(ctx)
    assert ctx.bot.edited_messages == []


async def test_picking_a_month_returns_to_the_day_grid_for_that_year_and_month():
    _reset()
    ctx = _ctx(
        FakeTelegramUpdate(
            callback_data=f"cal:{_TEST_PURPOSE}:month:202612",
            callback_query=FakeCallbackQuery(message=FakeCallbackMessage(message_id=7)),
        )
    )

    await calendar_widget.handle_calendar_callback(ctx)

    edited = ctx.bot.edited_messages[0]
    labels = [b["text"] for row in edited["reply_markup"]["inline_keyboard"] for b in row]
    assert "December 2026" in labels  # the day grid's own caption/month-picker button
    assert _results == []  # picking a month is navigation, not a resolved date


# --- dynamic (callable) prompts --------------------------------------------


async def test_callable_prompt_is_used_as_is_for_the_initial_render():
    global _dynamic_prompt_text
    _reset()
    _dynamic_prompt_text = "initial render"
    ctx = _ctx(
        FakeTelegramUpdate(callback_data="whatever", callback_query=FakeCallbackQuery(message=FakeCallbackMessage(message_id=7)))
    )

    await calendar_widget.start_calendar_flow(ctx, purpose=_DYNAMIC_PURPOSE, anchor=date(2026, 9, 1))

    assert ctx.bot.edited_messages[-1]["text"] == "initial render"


async def test_callable_prompt_reflects_updated_value_between_two_renders():
    global _dynamic_prompt_text
    _reset()

    _dynamic_prompt_text = "before"
    ctx1 = _ctx(
        FakeTelegramUpdate(callback_data="whatever", callback_query=FakeCallbackQuery(message=FakeCallbackMessage(message_id=7)))
    )
    await calendar_widget.start_calendar_flow(ctx1, purpose=_DYNAMIC_PURPOSE, anchor=date(2026, 9, 1))
    assert ctx1.bot.edited_messages[-1]["text"] == "before"

    _dynamic_prompt_text = "after"
    ctx2 = _ctx(
        FakeTelegramUpdate(
            callback_data=f"cal:{_DYNAMIC_PURPOSE}:prev:202609", callback_query=FakeCallbackQuery(message=FakeCallbackMessage(message_id=7))
        )
    )
    await calendar_widget.handle_calendar_callback(ctx2)
    assert ctx2.bot.edited_messages[-1]["text"] == "after"
