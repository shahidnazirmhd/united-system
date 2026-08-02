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
from apps.leave.application.ports import EmployeeLookupPort, EmployeeStatusPort


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

    # --- Approval Engine (Phase 9) ---------------------------------------
    def get_manager_employee_id(self, employee_id: uuid.UUID) -> uuid.UUID | None:
        try:
            response = employees_dependencies.build_employee_service().get_by_id(employee_id)
        except EmployeeNotFoundError:
            return None
        return response.manager_id

    def is_employee_linked_to_telegram(self, employee_id: uuid.UUID) -> bool:
        try:
            response = employees_dependencies.build_employee_service().get_by_id(employee_id)
        except EmployeeNotFoundError:
            return False
        return response.is_linked_to_telegram

    # --- HR-wide leave request list (Phase 13 review requirement) --------
    def get_employee_display_info(self, employee_id: uuid.UUID) -> tuple[str, str] | None:
        try:
            response = employees_dependencies.build_employee_service().get_by_id(employee_id)
        except EmployeeNotFoundError:
            return None
        return response.full_name, response.employee_code

    # --- Leave eligibility (round 14 item 6) ------------------------------
    def is_employee_eligible_for_leave(self, employee_id: uuid.UUID) -> bool:
        try:
            response = employees_dependencies.build_employee_service().get_by_id(employee_id)
        except EmployeeNotFoundError:
            return False
        return response.is_eligible_for_leave

    # --- Daily status reconciliation (round 14 items 6/8) -----------------
    def list_employee_ids_on_leave_status(self) -> list[uuid.UUID]:
        return employees_dependencies.build_employee_service().list_employee_ids_by_current_status(
            ["sick_leave", "annual_leave"]
        )

    # --- Leave cancellation notification (round 15 item 6) -----------------
    def get_telegram_chat_id(self, employee_id: uuid.UUID) -> int | None:
        try:
            response = employees_dependencies.build_employee_service().get_by_id(employee_id)
        except EmployeeNotFoundError:
            return None
        return response.telegram_chat_id


class EmployeeStatusServiceAdapter(EmployeeStatusPort):
    """Adapter implementing `EmployeeStatusPort` (round 14 items 6/8)
    against `apps.employees`'s already-composed public `EmployeeService` —
    same discipline as `EmployeeServiceLookupAdapter` above, just for a
    mutating call instead of a read."""

    def enter_leave_status(self, employee_id: uuid.UUID, leave_status: str) -> None:
        employees_dependencies.build_employee_service().enter_leave_status(employee_id, leave_status)

    def exit_leave_status(self, employee_id: uuid.UUID) -> None:
        employees_dependencies.build_employee_service().exit_leave_status(employee_id)
