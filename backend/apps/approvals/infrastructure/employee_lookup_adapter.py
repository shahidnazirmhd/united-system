"""Adapter implementing `apps.approvals.application.ports.EmployeeLookupPort`
against `apps.employees`'s already-composed public `EmployeeService`.

This is the one file in this module allowed to import `apps.employees` —
and even here, only its public composition root
(`apps.employees.interface.dependencies.build_employee_service`) and public
domain exceptions, never its infrastructure repositories or ORM models
directly. Same discipline as
`apps.leave.infrastructure.employee_lookup_adapter.EmployeeServiceLookupAdapter`,
kept as this module's own separate class rather than reusing Leave's —
this module must not import Leave (or depend on Leave existing at all).
"""
from __future__ import annotations

import uuid

from apps.employees.domain.exceptions import EmployeeNotFoundError, EmployeeNotLinkedToTelegramError
from apps.employees.interface import dependencies as employees_dependencies
from apps.approvals.application.ports import EmployeeLookupPort


class EmployeeServiceLookupAdapter(EmployeeLookupPort):
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

    def get_telegram_chat_id(self, employee_id: uuid.UUID) -> int | None:
        try:
            response = employees_dependencies.build_employee_service().get_by_id(employee_id)
        except EmployeeNotFoundError:
            return None
        return response.telegram_chat_id

    def get_employee_display_info(self, employee_id: uuid.UUID) -> tuple[str, str] | None:
        try:
            response = employees_dependencies.build_employee_service().get_by_id(employee_id)
        except EmployeeNotFoundError:
            return None
        return response.full_name, response.employee_code
