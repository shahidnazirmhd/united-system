"""Leave balance reads plus the internal mutation methods that back
approve/cancel-of-approved and new-employee auto-provisioning.

Not built on `BaseService` — `LeaveBalance` has no single natural "id" the
API operates on (every read/write is keyed by employee+leave_type+year, a
composite the generic base doesn't model), and there is no "create/update a
balance" endpoint in this phase's brief at all. A hand-written service,
matching Identity's original per-purpose-class precedent, is the better fit
here (see this phase's architecture notes).
"""
from __future__ import annotations

import uuid
from decimal import Decimal

from apps.leave.application.dtos import LeaveBalanceResponse
from apps.leave.application.mappers import leave_balance_to_response
from apps.leave.domain.entities import LeaveBalance, LeaveType
from apps.leave.domain.repositories import LeaveBalanceRepository, LeaveRequestRepository, LeaveTypeRepository
from shared_kernel.application.unit_of_work import UnitOfWork
from shared_kernel.infrastructure.uuid7 import generate_uuid7


class LeaveBalanceService:
    def __init__(
        self,
        leave_balance_repository: LeaveBalanceRepository,
        leave_type_repository: LeaveTypeRepository,
        leave_request_repository: LeaveRequestRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._balances = leave_balance_repository
        self._leave_types = leave_type_repository
        self._requests = leave_request_repository
        self._uow = unit_of_work

    # --- reads ------------------------------------------------------
    def get_balance(
        self, *, employee_id: uuid.UUID, leave_type_id: uuid.UUID, year: int
    ) -> LeaveBalanceResponse:
        """Returns a zeroed response (not a 404) when no balance row exists
        yet — a brand-new employee whose `EmployeeCreated` provisioning
        hasn't run yet (or a leave type added after the employee joined)
        should see "0 available," not an error, when checking their
        balance. See `domain/exceptions.py:LeaveBalanceNotFoundError`'s
        docstring for the (currently unused) strict alternative.
        """
        leave_type = self._leave_types.get_by_id(leave_type_id)
        balance = self._balances.get_by_employee_leave_type_year(
            employee_id=employee_id, leave_type_id=leave_type_id, year=year
        )
        pending = self._requests.sum_pending_days(employee_id=employee_id, leave_type_id=leave_type_id, year=year)
        if balance is None:
            balance = LeaveBalance(
                id=generate_uuid7(), employee_id=employee_id, leave_type_id=leave_type_id, year=year
            )
        return leave_balance_to_response(
            balance, leave_type_name=leave_type.name if leave_type is not None else None, pending_days=pending
        )

    def list_balances(self, *, employee_id: uuid.UUID, year: int) -> list[LeaveBalanceResponse]:
        """One row per leave type the employee has ever had a balance
        provisioned for, plus every currently-active leave type that has no
        row yet (zeroed) — so a newly-added leave type shows up immediately
        for every employee, not only after their next `EmployeeCreated`
        event (which, being provisioned only at creation time, never fires
        again for existing employees).
        """
        existing_by_type = {
            b.leave_type_id: b
            for b in self._balances.list_by_employee(employee_id=employee_id, year=year)
        }
        responses: list[LeaveBalanceResponse] = []
        for leave_type in self._leave_types.list_active():
            balance = existing_by_type.get(leave_type.id) or LeaveBalance(
                id=generate_uuid7(), employee_id=employee_id, leave_type_id=leave_type.id, year=year
            )
            pending = self._requests.sum_pending_days(
                employee_id=employee_id, leave_type_id=leave_type.id, year=year
            )
            responses.append(leave_balance_to_response(balance, leave_type_name=leave_type.name, pending_days=pending))
        return responses

    # --- writes (internal — called by LeaveRequestService and the
    # EmployeeCreated subscriber, never directly by the interface layer) --
    def provision_initial_balance(self, *, employee_id: uuid.UUID, leave_type: LeaveType, year: int) -> None:
        """Creates a `LeaveBalance` row seeded from `leave_type.default_annual_days`
        if one doesn't already exist for this employee/type/year — a no-op
        otherwise (idempotent, so re-delivery of `EmployeeCreated` — the
        in-process bus doesn't currently retry, but a future durable one
        might — can never double-provision)."""
        existing = self._balances.get_by_employee_leave_type_year(
            employee_id=employee_id, leave_type_id=leave_type.id, year=year
        )
        if existing is not None:
            return
        with self._uow:
            self._balances.create(
                LeaveBalance(
                    id=generate_uuid7(),
                    employee_id=employee_id,
                    leave_type_id=leave_type.id,
                    year=year,
                    entitled_days=leave_type.default_annual_days,
                )
            )

    def increase_used_days(self, *, employee_id: uuid.UUID, leave_type_id: uuid.UUID, year: int, amount: Decimal) -> None:
        balance = self._balances.get_by_employee_leave_type_year(
            employee_id=employee_id, leave_type_id=leave_type_id, year=year
        )
        if balance is None:
            # Approving a request against a balance row that was never
            # provisioned (e.g. leave type added after the employee's
            # EmployeeCreated event already fired) — create it on the fly
            # rather than failing the approval, with zero entitlement so
            # the deficit is visible on the next balance read.
            balance = LeaveBalance(
                id=generate_uuid7(), employee_id=employee_id, leave_type_id=leave_type_id, year=year
            )
            with self._uow:
                self._balances.create(balance.increase_used_days(amount))
            return
        with self._uow:
            self._balances.update(balance.increase_used_days(amount))

    def decrease_used_days(self, *, employee_id: uuid.UUID, leave_type_id: uuid.UUID, year: int, amount: Decimal) -> None:
        balance = self._balances.get_by_employee_leave_type_year(
            employee_id=employee_id, leave_type_id=leave_type_id, year=year
        )
        if balance is None:
            return
        with self._uow:
            self._balances.update(balance.decrease_used_days(amount))
