"""Outbound ports for the Attendance application layer.

`LeaveReferenceCheckPort` is a *reverse* port relative to Attendance's
existing role in this codebase: every other cross-module dependency so far
has Leave depending on Attendance (see `apps.leave.application.ports
.HolidayLookupPort` / `apps.leave.infrastructure.holiday_lookup_adapter
.HolidayServiceLookupAdapter` — Leave reads holiday dates to compute
working days). Round 15 item 3 needs the opposite direction: before
Attendance mutates a Holiday (edit or deactivate — there is no hard delete;
see `HolidayCommandService`), it must ask Leave "does any real leave
request still depend on this date." That fact is only known inside Leave,
so Dependency Inversion still applies here exactly as it does everywhere
else in this codebase — Attendance defines the port it needs, and the
concrete adapter (`infrastructure/leave_reference_check_adapter.py`) is the
only file in this module allowed to import `apps.leave`, and even then only
its public composition root (`apps.leave.interface.dependencies
.build_leave_service`), never that module's infrastructure directly. This
is a deliberate, judged exception to "always keep modules independent" —
the validation must live in the module owning the mutated resource
(Attendance), but the fact needed to make that decision is only known by
the module that consumes the resource (Leave).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date


class LeaveReferenceCheckPort(ABC):
    @abstractmethod
    def has_active_leave_request_covering_date(self, target_date: date) -> bool:
        """True if any PENDING/APPROVED leave request's date range includes
        `target_date` — used by `HolidayCommandService.validate_update` to
        block editing or deactivating a Holiday still relied upon by a real
        leave request."""
        raise NotImplementedError
