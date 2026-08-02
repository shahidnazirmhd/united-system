"""Adapter implementing `HolidayLookupPort` against `apps.attendance`'s
already-composed public `HolidayService` — same discipline as
`employee_lookup_adapter.py`'s `EmployeeServiceLookupAdapter`: this is the
one file in this module allowed to import `apps.attendance`, and even then
only its public composition root, never its infrastructure directly.
"""
from __future__ import annotations

from datetime import date

from apps.attendance.interface import dependencies as attendance_dependencies
from apps.leave.application.ports import HolidayLookupPort


class HolidayServiceLookupAdapter(HolidayLookupPort):
    def get_holiday_dates_in_range(self, *, start_date: date, end_date: date) -> frozenset[date]:
        return attendance_dependencies.build_holiday_service().get_dates_in_range(
            start_date=start_date, end_date=end_date
        )
