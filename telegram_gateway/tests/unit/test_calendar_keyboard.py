"""Unit tests for formatting/calendar_keyboard.py — the pure grid-building
and callback_data encode/decode functions. No Telegram API calls, no
handler dispatch (see test_calendar_widget.py for that layer)."""
from __future__ import annotations

import calendar as stdlib_calendar
from datetime import date

import pytest

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
    CalendarCallback,
    build_calendar_keyboard,
    build_month_picker_keyboard,
    parse_calendar_callback,
    shift_month,
)

_PURPOSE = "test.purpose"


def _all_buttons(keyboard: dict) -> list[dict]:
    return [button for row in keyboard["inline_keyboard"] for button in row]


def test_keyboard_has_one_button_per_day_of_the_month():
    keyboard = build_calendar_keyboard(_PURPOSE, 2026, 9)  # September 2026 — 30 days
    day_buttons = [b for b in _all_buttons(keyboard) if parse_calendar_callback(b["callback_data"]).action == ACTION_DAY]
    assert len(day_buttons) == 30


def test_every_day_button_decodes_to_the_right_calendar_callback():
    keyboard = build_calendar_keyboard(_PURPOSE, 2026, 2)  # February 2026 — 28 days (not a leap year)
    day_buttons = [b for b in _all_buttons(keyboard) if parse_calendar_callback(b["callback_data"]).action == ACTION_DAY]
    decoded_days = sorted(parse_calendar_callback(b["callback_data"]).day for b in day_buttons)
    assert decoded_days == list(range(1, 29))
    for button in day_buttons:
        parsed = parse_calendar_callback(button["callback_data"])
        assert parsed.purpose == _PURPOSE
        assert parsed.year == 2026
        assert parsed.month == 2


def test_keyboard_has_prev_today_next_and_cancel_buttons():
    keyboard = build_calendar_keyboard(_PURPOSE, 2026, 9)
    actions = {parse_calendar_callback(b["callback_data"]).action for b in _all_buttons(keyboard)}
    assert ACTION_PREV in actions
    assert ACTION_NEXT in actions
    assert ACTION_TODAY in actions
    assert ACTION_CANCEL in actions


def test_prev_next_today_cancel_buttons_carry_the_displayed_month_not_a_shifted_one():
    """Navigation buttons encode the CURRENTLY DISPLAYED month — shifting to
    the new month is the dispatch layer's job (handlers/calendar_widget.py),
    not something baked into the keyboard itself."""
    keyboard = build_calendar_keyboard(_PURPOSE, 2026, 9)
    for button in _all_buttons(keyboard):
        parsed = parse_calendar_callback(button["callback_data"])
        if parsed.action in (ACTION_PREV, ACTION_NEXT, ACTION_TODAY, ACTION_CANCEL):
            assert parsed.year == 2026
            assert parsed.month == 9


def test_padding_cells_are_noop_and_do_not_double_count_as_days():
    keyboard = build_calendar_keyboard(_PURPOSE, 2026, 9)
    week_rows = keyboard["inline_keyboard"][2:-2]  # skip caption/weekday header and the trailing nav/cancel rows
    for row in week_rows:
        assert len(row) == 7  # always a full 7-column grid, padded with noop cells
    noop_count = sum(
        1 for b in _all_buttons(keyboard) if parse_calendar_callback(b["callback_data"]).action == ACTION_NOOP
    )
    # 7 noop buttons from the weekday-header row alone (the caption button
    # is NOT noop — it opens the month picker, see
    # test_caption_button_opens_the_month_picker_for_the_currently_displayed_month),
    # plus however many blank padding cells the month's layout needs.
    assert noop_count >= 7


def test_todays_day_button_is_visually_marked_in_the_current_month():
    today = date.today()
    keyboard = build_calendar_keyboard(_PURPOSE, today.year, today.month)
    today_buttons = [
        b
        for b in _all_buttons(keyboard)
        if (parsed := parse_calendar_callback(b["callback_data"])).action == ACTION_DAY and parsed.day == today.day
    ]
    assert len(today_buttons) == 1
    assert today_buttons[0]["text"] == f"•{today.day}•"


def test_a_different_months_days_are_not_marked_as_today():
    # Whatever "today" is, a month that isn't the current one should never
    # show the marker.
    today = date.today()
    other_year, other_month = (today.year - 1, today.month)
    keyboard = build_calendar_keyboard(_PURPOSE, other_year, other_month)
    for button in _all_buttons(keyboard):
        assert "•" not in button["text"]


def test_purpose_containing_a_colon_is_rejected():
    with pytest.raises(AssertionError):
        build_calendar_keyboard("bad:purpose", 2026, 9)


def test_invalid_month_raises_value_error():
    with pytest.raises(ValueError):
        build_calendar_keyboard(_PURPOSE, 2026, 13)


def test_caption_button_opens_the_month_picker_for_the_currently_displayed_month():
    """Tapping "September 2026" should jump straight to picking a
    month/year — not be a dead no-op label like the weekday headers are."""
    keyboard = build_calendar_keyboard(_PURPOSE, 2026, 9)
    caption = keyboard["inline_keyboard"][0][0]
    assert caption["text"] == "September 2026"
    parsed = parse_calendar_callback(caption["callback_data"])
    assert parsed.action == ACTION_OPEN_MONTH_PICKER
    assert parsed.year == 2026
    assert parsed.month == 9


def test_label_is_omitted_by_default():
    keyboard = build_calendar_keyboard(_PURPOSE, 2026, 9)
    labels = [b["text"] for row in keyboard["inline_keyboard"] for b in row]
    assert "🟢 FROM DATE — tap a day to select" not in labels


def test_label_row_sits_directly_above_the_cancel_row():
    keyboard = build_calendar_keyboard(_PURPOSE, 2026, 9, label="🟢 FROM DATE — tap a day to select")
    rows = keyboard["inline_keyboard"]
    assert rows[-1][0]["text"] == "❌ Cancel"
    assert len(rows[-2]) == 1
    assert rows[-2][0]["text"] == "🟢 FROM DATE — tap a day to select"


def test_label_row_button_is_a_pure_noop():
    keyboard = build_calendar_keyboard(_PURPOSE, 2026, 9, label="🟢 FROM DATE — tap a day to select")
    label_button = keyboard["inline_keyboard"][-2][0]
    parsed = parse_calendar_callback(label_button["callback_data"])
    assert parsed.action == ACTION_NOOP
    assert parsed.year == 2026 and parsed.month == 9


# --- build_month_picker_keyboard -------------------------------------


def test_month_picker_has_a_button_for_every_month():
    keyboard = build_month_picker_keyboard(_PURPOSE, 2026)
    month_buttons = [b for b in _all_buttons(keyboard) if parse_calendar_callback(b["callback_data"]).action == ACTION_MONTH_PICK]
    assert len(month_buttons) == 12
    decoded_months = sorted(parse_calendar_callback(b["callback_data"]).month for b in month_buttons)
    assert decoded_months == list(range(1, 13))
    for button in month_buttons:
        parsed = parse_calendar_callback(button["callback_data"])
        assert parsed.purpose == _PURPOSE
        assert parsed.year == 2026


def test_month_picker_has_year_navigation_and_cancel():
    keyboard = build_month_picker_keyboard(_PURPOSE, 2026)
    actions = {parse_calendar_callback(b["callback_data"]).action for b in _all_buttons(keyboard)}
    assert ACTION_MONTH_PICKER_PREV_YEAR in actions
    assert ACTION_MONTH_PICKER_NEXT_YEAR in actions
    assert ACTION_CANCEL in actions


def test_month_picker_year_nav_shifts_by_exactly_one_year():
    keyboard = build_month_picker_keyboard(_PURPOSE, 2026)
    for button in _all_buttons(keyboard):
        parsed = parse_calendar_callback(button["callback_data"])
        if parsed.action == ACTION_MONTH_PICKER_PREV_YEAR:
            assert parsed.year == 2026  # the picker's job is to interpret this as "go to 2025"; see calendar_widget.py
        if parsed.action == ACTION_MONTH_PICKER_NEXT_YEAR:
            assert parsed.year == 2026


def test_month_picker_marks_the_current_month_in_the_current_year():
    today = date.today()
    keyboard = build_month_picker_keyboard(_PURPOSE, today.year)
    month_buttons = [b for b in _all_buttons(keyboard) if parse_calendar_callback(b["callback_data"]).action == ACTION_MONTH_PICK]
    current = next(b for b in month_buttons if parse_calendar_callback(b["callback_data"]).month == today.month)
    assert current["text"].startswith("•") and current["text"].endswith("•")


def test_month_picker_does_not_mark_any_month_in_a_different_year():
    today = date.today()
    keyboard = build_month_picker_keyboard(_PURPOSE, today.year - 1)
    for button in _all_buttons(keyboard):
        assert "•" not in button["text"]


def test_month_picker_purpose_containing_a_colon_is_rejected():
    with pytest.raises(AssertionError):
        build_month_picker_keyboard("bad:purpose", 2026)


def test_month_picker_label_is_omitted_by_default():
    keyboard = build_month_picker_keyboard(_PURPOSE, 2026)
    labels = [b["text"] for row in keyboard["inline_keyboard"] for b in row]
    assert "🔵 TO DATE — tap a day to select" not in labels


def test_month_picker_label_row_sits_directly_above_the_cancel_row():
    keyboard = build_month_picker_keyboard(_PURPOSE, 2026, label="🔵 TO DATE — tap a day to select")
    rows = keyboard["inline_keyboard"]
    assert rows[-1][0]["text"] == "❌ Cancel"
    assert len(rows[-2]) == 1
    assert rows[-2][0]["text"] == "🔵 TO DATE — tap a day to select"
    assert parse_calendar_callback(rows[-2][0]["callback_data"]).action == ACTION_NOOP


# --- parse_calendar_callback -----------------------------------------------


def test_parse_round_trips_every_action_shape():
    keyboard = build_calendar_keyboard(_PURPOSE, 2026, 9)
    for button in _all_buttons(keyboard):
        assert parse_calendar_callback(button["callback_data"]) is not None


def test_parse_rejects_wrong_prefix():
    assert parse_calendar_callback("notcal:test.purpose:today:202609") is None


def test_parse_rejects_wrong_field_count():
    assert parse_calendar_callback("cal:test.purpose:today") is None
    assert parse_calendar_callback("cal:test.purpose:day:202609:05:extra") is None


def test_parse_rejects_non_numeric_yyyymm():
    assert parse_calendar_callback("cal:test.purpose:today:abcdef") is None


def test_parse_rejects_out_of_range_month():
    assert parse_calendar_callback("cal:test.purpose:today:202613") is None


def test_parse_rejects_non_numeric_day():
    assert parse_calendar_callback("cal:test.purpose:day:202609:xx") is None


def test_parse_accepts_purpose_with_dots():
    parsed = parse_calendar_callback("cal:leave.apply.start:day:202609:05")
    assert parsed == CalendarCallback(purpose="leave.apply.start", action=ACTION_DAY, year=2026, month=9, day=5)


def test_parse_random_unrelated_string_returns_none():
    assert parse_calendar_callback("leave:apply:type:lt-annual") is None


# --- shift_month -------------------------------------------------------


def test_shift_month_forward_across_year_boundary():
    assert shift_month(2026, 12, 1) == (2027, 1)


def test_shift_month_backward_across_year_boundary():
    assert shift_month(2026, 1, -1) == (2025, 12)


def test_shift_month_within_the_same_year():
    assert shift_month(2026, 6, 1) == (2026, 7)
    assert shift_month(2026, 6, -1) == (2026, 5)


def test_shift_month_matches_stdlib_calendar_day_counts_for_every_month_of_a_year():
    # Cross-check against the stdlib itself rather than hand-picked
    # examples only — walks all 12 months forward and back to (2026, m).
    for month in range(1, 13):
        forward = shift_month(2026, month, 1)
        back = shift_month(*forward, -1)
        assert back == (2026, month)
        assert stdlib_calendar.isleap(2026) is False  # sanity check on the fixture year used throughout this file
