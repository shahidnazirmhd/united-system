"""Adapter implementing `EmployeeLookupPort` against `apps.employees`'s
already-composed public `EmployeeService`.

This is the one file in this module allowed to import `apps.employees` —
and even here, only its public composition root
(`apps.employees.interface.dependencies.build_employee_service`) and public
domain exceptions, never its infrastructure repositories or ORM models
directly. That distinction is the whole point: Leave depends on Employees'
*public contract*, so a future internal refactor of Employees (swap its
repository implementation, change its ORM schema) can never break Leave as
long as `EmployeeService`'s public methods keep their meaning.
"""
from __future__ import annotations

import uuid

from apps.employees.domain.exceptions import EmployeeNotFoundError, EmployeeNotLinkedToTelegramError
from apps.employees.interface import dependencies as employees_dependencies
from apps.leave.application.ports import EmployeeLookupPort


class EmployeeServiceLookupAdapter(EmployeeLookupPort):
    def employee_exists(self, employee_id: uuid.UUID) -> bool:
        try:
            employees_dependencies.build_employee_service().get_by_id(employee_id)
        except EmployeeNotFoundError:
            return False
        return True

    def get_employee_id_by_user_id(self, user_id: uuid.UUID) -> uuid.UUID | None:
        try:
            response = employees_dependencies.build_employee_service().get_my_profile(user_id)
        except EmployeeNotFoundError:
            return None
        return response.id

    def get_employee_id_by_telegram_user_id(self, telegram_user_id: int) -> uuid.UUID | None:
        try:
            response = employees_dependencies.build_employee_service().get_profile_by_telegram_user_id(
                telegram_user_id
            )
        except EmployeeNotLinkedToTelegramError:
            return None
        return response.id
