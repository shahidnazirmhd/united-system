"""Adapter implementing `LeaveReferenceCheckPort` against `apps.leave`'s
already-composed public `LeaveService` — mirrors
`apps.attendance.infrastructure.leave_reference_check_adapter
.LeaveServiceReferenceCheckAdapter` exactly. The one file in this module
allowed to import `apps.leave`, and even then only its public composition
root, never its infrastructure directly.
"""
from __future__ import annotations

from apps.settings.application.ports import LeaveReferenceCheckPort
from apps.leave.interface import dependencies as leave_dependencies


class LeaveServiceReferenceCheckAdapter(LeaveReferenceCheckPort):
    def has_any_active_leave_request(self) -> bool:
        return leave_dependencies.build_leave_service().has_any_active_request()
