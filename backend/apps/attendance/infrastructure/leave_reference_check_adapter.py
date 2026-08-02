"""Adapter implementing `LeaveReferenceCheckPort` against `apps.leave`'s
already-composed public `LeaveService` — same discipline as
`apps.leave.infrastructure.holiday_lookup_adapter.HolidayServiceLookupAdapter`
running in the reverse direction: this is the one file in this module
allowed to import `apps.leave`, and even then only its public composition
root, never its infrastructure directly.
"""
from __future__ import annotations

from datetime import date

from apps.attendance.application.ports import LeaveReferenceCheckPort
from apps.leave.interface import dependencies as leave_dependencies


class LeaveServiceReferenceCheckAdapter(LeaveReferenceCheckPort):
    def has_active_leave_request_covering_date(self, target_date: date) -> bool:
        return leave_dependencies.build_leave_service().has_active_request_covering_date(target_date)
