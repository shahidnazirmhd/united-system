"""Round 14 item 6 — computes working days within a leave date range,
excluding the configured weekly day off and any holiday dates.

Plain Python, no Django/framework import — matching every other file under
`domain/`. Deliberately takes `week_off_weekday`/`holiday_dates` as plain
parameters rather than reaching into `apps.settings`/`apps.attendance`
itself: the domain layer never depends on infrastructure or other modules
(see `application/services/leave_validation_service.py`'s own reasoning for
`allow_past_start_date` being injected the same way). The caller
(`LeaveRequestService.apply_leave`) is what resolves those two values
through `SettingsLookupPort`/`HolidayLookupPort` first.
"""
from __future__ import annotations

from datetime import date, timedelta

from shared_kernel.domain.value_objects import DateRange


def calculate_working_days(
    date_range: DateRange, *, week_off_weekday: int, holiday_dates: frozenset[date]
) -> int:
    """`week_off_weekday` matches `date.weekday()`'s convention (0=Monday
    ... 6=Sunday) — the same convention `apps.settings`'s
    `default_week_off` setting is stored in (see that module's seed
    migration). A day that is BOTH the week-off day AND a holiday is only
    excluded once (not double-counted as two separate exclusions) — the
    loop below already treats "excluded" as a single boolean per day, so
    this falls out naturally rather than needing special-casing.
    """
    working_days = 0
    current = date_range.start_date
    one_day = timedelta(days=1)
    while current <= date_range.end_date:
        is_week_off = current.weekday() == week_off_weekday
        is_holiday = current in holiday_dates
        if not is_week_off and not is_holiday:
            working_days += 1
        current += one_day
    return working_days
