"""Reusable Telegram inline calendar date picker — the pure, stateless
half. This file only ever builds an `InlineKeyboardMarkup`-shaped dict for
a given month and encodes/decodes the callback_data that grid produces; it
never calls the Telegram Bot API and knows nothing about Leave or any other
HR module. `handlers/calendar_widget.py` is the other half — it wires this
into the command registry and resolves a tapped date back to whichever
module asked for it.

Built entirely from the standard library `calendar` module — deliberately
no third-party calendar package.

Every button's callback_data is one string:

    cal:{purpose}:{action}:{yyyymm}[:{day}]

`purpose` is an opaque, caller-supplied identifier (e.g. "leave.apply.start")
that namespaces which flow asked for a date — this is the entire mechanism
that makes the widget reusable across modules rather than Leave-specific;
a future Attendance or Payroll flow just picks its own purpose string and
never touches this file. `purpose` must not itself contain ':' (reserved
here as the field separator) — use '.' or '_' inside a purpose string
instead, e.g. "leave.apply.start".
"""
from __future__ import annotations

import calendar as _calendar
from dataclasses import dataclass
from datetime import date
from typing import Any

ACTION_DAY = "day"
ACTION_PREV = "prev"
ACTION_NEXT = "next"
ACTION_TODAY = "today"
ACTION_CANCEL = "cancel"
ACTION_NOOP = "noop"

# Month/year picker (opened by tapping the day-grid's own month/year
# caption) — jumping straight to, say, December 2027 by tapping Next 15
# times is not "easy," so this is a second, smaller view: 12 month buttons
# for one year at a time, with its own year-only Prev/Next.
ACTION_OPEN_MONTH_PICKER = "open_month"
ACTION_MONTH_PICK = "month"
ACTION_MONTH_PICKER_PREV_YEAR = "month_prev_year"
ACTION_MONTH_PICKER_NEXT_YEAR = "month_next_year"

_PREFIX = "cal"

# The stdlib `calendar` module doesn't itself bound years (month-day
# arithmetic for year 0 or negative years "works" without raising), so
# without an explicit limit, repeatedly tapping Prev would page backward
# forever into nonsensical years. There's no real HR use case (leave,
# attendance, payroll, ...) needing a date outside this range, so
# handlers/calendar_widget.py's navigation stops here instead.
MIN_YEAR = 1970
MAX_YEAR = 2100

# Hardcoded rather than `calendar.month_name`/`calendar.day_abbr` — those
# depend on the process locale, which is not something this service
# controls or wants a Telegram message's wording to depend on.
_MONTH_NAMES = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]
_MONTH_ABBREVIATIONS = [
    "", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]
_WEEKDAY_HEADERS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]


@dataclass(frozen=True)
class CalendarCallback:
    purpose: str
    action: str
    year: int
    month: int
    day: int | None = None


def _encode(purpose: str, action: str, year: int, month: int, day: int | None = None) -> str:
    assert ":" not in purpose, "calendar purpose strings may not contain ':' (reserved as the field separator)"
    parts = [_PREFIX, purpose, action, f"{year:04d}{month:02d}"]
    if day is not None:
        parts.append(f"{day:02d}")
    return ":".join(parts)


def parse_calendar_callback(data: str) -> CalendarCallback | None:
    """Returns None for anything that doesn't look like this widget's own
    callback_data, rather than raising — stale callback_data from an old,
    since-replaced inline keyboard is an expected occurrence (same
    "unregistered/expired button" category `handlers/registry.py`'s own
    unknown-callback fallback already handles), not a bug."""
    parts = data.split(":")
    if len(parts) not in (4, 5) or parts[0] != _PREFIX:
        return None
    _, purpose, action, yyyymm, *rest = parts
    if len(yyyymm) != 6 or not yyyymm.isdigit():
        return None
    year, month = int(yyyymm[:4]), int(yyyymm[4:])
    if not 1 <= month <= 12:
        return None
    day: int | None = None
    if rest:
        if not rest[0].isdigit():
            return None
        day = int(rest[0])
    return CalendarCallback(purpose=purpose, action=action, year=year, month=month, day=day)


def shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    """`delta` months from (year, month) — e.g. delta=-1 from (2026, 1) is
    (2025, 12). Pure arithmetic; the caller is responsible for handling a
    ValueError if the resulting (year, month) is outside what `date` can
    represent (see `build_calendar_keyboard`)."""
    index = (year * 12 + (month - 1)) + delta
    return index // 12, index % 12 + 1


def build_calendar_keyboard(purpose: str, year: int, month: int, *, label: str | None = None) -> dict[str, Any]:
    """A full month view: a month/year caption row, weekday initials, day-
    number buttons (Monday-first week, matching `calendar.Calendar`'s
    default), then a Prev / Today / Next row, an optional `label` row, and
    a Cancel row.

    `label` is opaque, caller-supplied plain text (Telegram button labels
    don't render Markdown) rendered as its own single-button row directly
    above Cancel — this widget has no opinion on what it says; a caller
    uses it to show which step of a multi-date flow this calendar belongs
    to (e.g. Leave's "🟢 FROM DATE — tap a day to select"), keeping that
    module-specific wording entirely out of this file. Omitted when `None`.

    Raises ValueError (via the stdlib `calendar` module) if `month` isn't
    1-12 or `year`/`month` falls outside what `datetime.date` can
    represent — callers navigating month-by-month should treat that as
    "can't go further," not a real error.
    """
    weeks = _calendar.Calendar(firstweekday=0).monthdayscalendar(year, month)
    today = date.today()
    is_current_month = (year, month) == (today.year, today.month)

    rows: list[list[dict[str, str]]] = [
        [
            {
                "text": f"{_MONTH_NAMES[month]} {year}",
                "callback_data": _encode(purpose, ACTION_OPEN_MONTH_PICKER, year, month),
            }
        ],
        [_noop_button(h, purpose=purpose, year=year, month=month) for h in _WEEKDAY_HEADERS],
    ]
    for week in weeks:
        row: list[dict[str, str]] = []
        for day in week:
            if day == 0:
                row.append(_noop_button(" ", purpose=purpose, year=year, month=month))
                continue
            day_label = f"•{day}•" if is_current_month and day == today.day else str(day)
            row.append({"text": day_label, "callback_data": _encode(purpose, ACTION_DAY, year, month, day)})
        rows.append(row)

    rows.append(
        [
            {"text": "◀ Prev", "callback_data": _encode(purpose, ACTION_PREV, year, month)},
            {"text": "Today", "callback_data": _encode(purpose, ACTION_TODAY, year, month)},
            {"text": "Next ▶", "callback_data": _encode(purpose, ACTION_NEXT, year, month)},
        ]
    )
    if label is not None:
        rows.append([_noop_button(label, purpose=purpose, year=year, month=month)])
    rows.append([{"text": "❌ Cancel", "callback_data": _encode(purpose, ACTION_CANCEL, year, month)}])
    return {"inline_keyboard": rows}


def build_month_picker_keyboard(purpose: str, year: int, *, label: str | None = None) -> dict[str, Any]:
    """The "jump straight to a month/year" view — opened by tapping the
    day-grid's own caption button. A year-only Prev/Next row (jumps 12
    months per tap, not one) followed by all 12 months of that year as
    buttons, so reaching e.g. December 2027 from "now" is two taps (Next
    year, Dec) instead of fifteen (Next month x15). Tapping a month
    returns to `build_calendar_keyboard` for that (year, month).

    `label` is the same opaque, caller-supplied footer row
    `build_calendar_keyboard` accepts — carried over here so the "which
    date am I picking" indicator stays visible while a caller detours
    through this view too, not just on the day grid."""
    today = date.today()
    rows: list[list[dict[str, str]]] = [
        [
            {"text": "◀", "callback_data": _encode(purpose, ACTION_MONTH_PICKER_PREV_YEAR, year, 1)},
            _noop_button(str(year), purpose=purpose, year=year, month=1),
            {"text": "▶", "callback_data": _encode(purpose, ACTION_MONTH_PICKER_NEXT_YEAR, year, 1)},
        ]
    ]
    for row_start in range(1, 13, 3):
        row: list[dict[str, str]] = []
        for m in range(row_start, row_start + 3):
            is_current = (year, m) == (today.year, today.month)
            month_label = f"•{_MONTH_ABBREVIATIONS[m]}•" if is_current else _MONTH_ABBREVIATIONS[m]
            row.append({"text": month_label, "callback_data": _encode(purpose, ACTION_MONTH_PICK, year, m)})
        rows.append(row)
    if label is not None:
        rows.append([_noop_button(label, purpose=purpose, year=year, month=1)])
    rows.append([{"text": "❌ Cancel", "callback_data": _encode(purpose, ACTION_CANCEL, year, 1)}])
    return {"inline_keyboard": rows}


def _noop_button(text: str, *, purpose: str, year: int, month: int) -> dict[str, str]:
    return {"text": text, "callback_data": _encode(purpose, ACTION_NOOP, year, month)}
