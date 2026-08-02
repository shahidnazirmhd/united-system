"""Domain entity -> response DTO mapping, shared by both the command and
query services so the shape sent back to the interface layer can never
drift between "just created/updated" and "read back later" (avoid
duplication — PROJECT_SPEC.md).
"""
from __future__ import annotations

from apps.employees.application.dtos import DepartmentResponse, EmployeeResponse
from apps.employees.domain.entities import Department, Employee


def employee_to_response(
    employee: Employee,
    *,
    department_name: str | None = None,
    manager_name: str | None = None,
    linked_user_email: str | None = None,
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
        last_working_date=employee.employment_info.last_working_date,  # round 15 item 9
        status=employee.status.value,
        department_name=department_name,
        manager_name=manager_name,
        linked_user_email=linked_user_email,
        is_linked_to_telegram=employee.is_linked_to_telegram,
        telegram_username=employee.telegram_username,
        telegram_linked_at=employee.telegram_linked_at,
        telegram_chat_id=employee.telegram_chat_id,
        current_status=employee.current_status.value,
        status_before_leave=employee.status_before_leave.value if employee.status_before_leave else None,
        is_eligible_for_leave=employee.is_eligible_for_leave,
    )


def department_to_response(
    department: Department,
    *,
    parent_department_name: str | None = None,
    head_employee_name: str | None = None,
) -> DepartmentResponse:
    return DepartmentResponse(
        id=department.id,
        name=department.name,
        code=department.code,
        parent_department_id=department.parent_department_id,
        head_employee_id=department.head_employee_id,
        is_active=department.is_active,
        parent_department_name=parent_department_name,
        head_employee_name=head_employee_name,
    )
