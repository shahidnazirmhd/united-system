"""Subscriber for `apps.employees.domain.events.EmployeeCreated`.

Registered by `apps/leave/apps.py`'s `ready()` hook. Lives in the interface
layer (not infrastructure) deliberately: this function plays the same
composition-root role `interface/dependencies.py` does — it needs the
already-composed `LeaveBalanceService` and `DjangoLeaveTypeRepository`
together, which is exactly the "wires application and infrastructure
together" responsibility that belongs at this layer, not inside
infrastructure itself (infrastructure code must not depend on how a whole
service is composed).
"""
from __future__ import annotations

import logging
from datetime import date

from apps.employees.domain.events import EmployeeCreated
from apps.leave.interface import dependencies

logger = logging.getLogger(__name__)


def handle_employee_created(event: EmployeeCreated) -> None:
    """Provisions one `LeaveBalance` row per currently-active `LeaveType`
    for the new employee, for the current calendar year, seeded from each
    type's `default_annual_days`. Idempotent (see
    `LeaveBalanceService.provision_initial_balance`) — safe to run more than
    once for the same employee without creating duplicate rows.
    """
    from apps.leave.infrastructure.repositories import DjangoLeaveTypeRepository

    balance_service = dependencies.build_leave_balance_service()
    year = date.today().year
    for leave_type in DjangoLeaveTypeRepository().list_active():
        balance_service.provision_initial_balance(employee_id=event.employee_id, leave_type=leave_type, year=year)

    logger.info("Provisioned initial leave balances for new employee=%s (year=%s)", event.employee_id, year)
