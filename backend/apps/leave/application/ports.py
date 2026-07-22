"""Outbound ports for the Leave application layer.

`EmployeeLookupPort` is how this module learns anything about an employee
without ever importing `apps.employees`'s domain/application layers, or
touching its database tables — the same Dependency Inversion already used
for `EmployeeOTPEmailPort` (apps/employees/application/ports.py), just
pointed at another module's public service instead of an external system
(SMTP). The concrete adapter (infrastructure/employee_lookup_adapter.py)
is the only file in this module allowed to import `apps.employees` at all,
and it imports that module's already-composed public `EmployeeService`
(via its own `interface/dependencies.py`), never its infrastructure
repositories directly — calling into another module's *public application
API* is the correct cross-module boundary in a modular monolith, not a
violation of "always keep modules independent."
"""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod


class EmployeeLookupPort(ABC):
    @abstractmethod
    def employee_exists(self, employee_id: uuid.UUID) -> bool:
        raise NotImplementedError

    @abstractmethod
    def get_employee_id_by_user_id(self, user_id: uuid.UUID) -> uuid.UUID | None:
        """Resolves the employee record linked to an Identity User account
        — used by the JWT-authenticated self-service endpoints (`.../me/`)
        to turn `request.user.user_id` into the employee id every Leave
        service method actually operates on."""
        raise NotImplementedError

    @abstractmethod
    def get_employee_id_by_telegram_user_id(self, telegram_user_id: int) -> uuid.UUID | None:
        """Resolves the employee linked to a Telegram account — used by the
        Gateway-facing `.../telegram/*` endpoints, mirroring
        `apps.employees.interface.telegram_views.EmployeeTelegramProfileView`'s
        resolution exactly."""
        raise NotImplementedError
