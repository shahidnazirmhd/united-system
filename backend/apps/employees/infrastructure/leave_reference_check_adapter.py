"""Adapter implementing `apps.employees.application.ports.LeaveReferenceCheckPort`
against `apps.leave`'s already-composed public `LeaveService` — same
discipline as `apps.attendance.infrastructure.leave_reference_check_adapter
.LeaveServiceReferenceCheckAdapter`/`apps.settings.infrastructure`'s own
copy of the same pattern: this is the one file in this module allowed to
import `apps.leave`, and even then only its public composition root, never
that module's infrastructure directly.

Unlike those two siblings, the import of `apps.leave.interface.dependencies`
here is deliberately LAZY (inside the method, not at module top). At
Django app-loading time, `apps.leave`'s own `AppConfig.ready()` imports
`apps.leave.infrastructure.approval_request_adapter`, which (transitively,
via `apps.approvals.interface.dependencies` -> `apps.approvals
.infrastructure.employee_lookup_adapter`) imports `apps.employees.interface
.dependencies` — which imports *this* file. A module-level import back to
`apps.leave.interface.dependencies` from here would close that loop back
onto `approval_request_adapter` while it's still mid-execution (its own
class not yet defined), raising a real `ImportError` at server startup
(confirmed via a real `pytest` run). Deferring the import to call time
breaks the cycle without weakening the "Employees depends on Leave's
public contract only" rule at all — it's still the one adapter method that
imports `apps.leave`, just resolved a moment later.
"""
from __future__ import annotations

import uuid

from apps.employees.application.ports import LeaveReferenceCheckPort


class LeaveServiceReferenceCheckAdapter(LeaveReferenceCheckPort):
    def has_active_or_upcoming_leave_request(self, employee_id: uuid.UUID) -> bool:
        from apps.leave.interface import dependencies as leave_dependencies

        return leave_dependencies.build_leave_service().has_active_or_upcoming_request_for_employee(employee_id)

    def has_active_or_upcoming_approved_leave(self, employee_id: uuid.UUID) -> bool:
        from apps.leave.interface import dependencies as leave_dependencies

        return leave_dependencies.build_leave_service().has_active_or_upcoming_approved_leave_for_employee(
            employee_id
        )
