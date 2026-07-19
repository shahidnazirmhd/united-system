"""Domain entity -> response DTO mapping, shared by both the command and
query services so the shape sent back to the interface layer can never
drift between "just created/updated" and "read back later" (avoid
duplication — PROJECT_SPEC.md).
"""
from __future__ import annotations

from apps.employees.application.dtos import EmployeeResponse
from apps.employees.domain.entities import Employee


def employee_to_response(
    employee: Employee, *, department_name: str | None = None, manager_name: str | None = None
) -> EmployeeResponse:
    return EmployeeResponse(
        id=employee.id,
        employee_code=employee.employee_code,
        user_id=employee.user_id,
        first_name=employee.profile.first_name,
        last_name=employee.profile.last_name,
        full_name=employee.profile.full_name,
        date_of_birth=employee.profile.date_of_birth,
        gender=employee.profile.gender,
        work_email=str(employee.contact_info.work_email),
        personal_email=str(employee.contact_info.personal_email) if employee.contact_info.personal_email else None,
        phone_number=employee.contact_info.phone_number,
        department_id=employee.employment_info.department_id,
        manager_id=employee.employment_info.manager_id,
        job_title=employee.employment_info.job_title,
        employment_type=employee.employment_info.employment_type.value,
        date_of_joining=employee.employment_info.date_of_joining,
        termination_date=employee.employment_info.termination_date,
        status=employee.status.value,
        department_name=department_name,
        manager_name=manager_name,
        is_linked_to_telegram=employee.is_linked_to_telegram,
        telegram_username=employee.telegram_username,
        telegram_linked_at=employee.telegram_linked_at,
    )
