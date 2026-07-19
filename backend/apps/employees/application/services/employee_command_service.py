"""Write side of the Employee module: create, update, activate, deactivate.

Built on shared_kernel's `BaseService` (transaction wrapping via UnitOfWork,
validate_create/validate_update hooks) rather than Identity's
one-class-per-use-case pattern — Employee's writes are closer to
straightforward CRUD-plus-a-couple-of-state-transitions than Identity's
genuinely distinct actions (login vs. password reset vs. role assignment),
so the generic base is the better fit here (see this phase's architecture
notes for the full reasoning).
"""
from __future__ import annotations

import uuid

from apps.employees.application.dtos import CreateEmployeeRequest, EmployeeResponse, UpdateEmployeeRequest
from apps.employees.application.mappers import employee_to_response
from apps.employees.domain.entities import Employee
from apps.employees.domain.enums import EmploymentType
from apps.employees.domain.events import EmployeeCreated, EmployeeStatusChanged, EmployeeUpdated
from apps.employees.domain.exceptions import (
    DepartmentNotFoundError,
    DuplicateWorkEmailError,
    EmployeeNotFoundError,
    UserAlreadyLinkedError,
)
from apps.employees.domain.repositories import DepartmentRepository, EmployeeRepository
from apps.employees.domain.value_objects import ContactInformation, EmployeeProfile, EmploymentInformation
from shared_kernel.application.base_service import BaseService
from shared_kernel.application.event_bus import EventBus
from shared_kernel.application.unit_of_work import UnitOfWork
from shared_kernel.domain.value_objects import Email
from shared_kernel.infrastructure.uuid7 import generate_uuid7


class EmployeeCommandService(BaseService[Employee]):
    not_found_exception = EmployeeNotFoundError

    def __init__(
        self,
        employee_repository: EmployeeRepository,
        department_repository: DepartmentRepository,
        unit_of_work: UnitOfWork,
        event_bus: EventBus,
    ) -> None:
        super().__init__(repository=employee_repository, unit_of_work=unit_of_work, event_bus=event_bus)
        self._employees = employee_repository
        self._departments = department_repository

    def create_employee(self, request: CreateEmployeeRequest) -> EmployeeResponse:
        employee = Employee(
            id=generate_uuid7(),
            employee_code=self._employees.next_employee_code(),
            user_id=request.user_id,
            profile=EmployeeProfile(
                first_name=request.first_name,
                last_name=request.last_name,
                date_of_birth=request.date_of_birth,
                gender=request.gender,
            ),
            contact_info=ContactInformation(
                work_email=Email(request.work_email),
                personal_email=Email(request.personal_email) if request.personal_email else None,
                phone_number=request.phone_number,
            ),
            employment_info=EmploymentInformation(
                department_id=request.department_id,
                manager_id=request.manager_id,
                job_title=request.job_title,
                employment_type=EmploymentType(request.employment_type),
                date_of_joining=request.date_of_joining,
            ),
        )
        created = self.create(employee)  # BaseService.create: validate_create -> uow -> repository.create -> after_create
        return employee_to_response(created)

    def update_employee(self, request: UpdateEmployeeRequest) -> EmployeeResponse:
        existing = self.get_by_id(request.employee_id)  # raises EmployeeNotFoundError if missing

        updated_entity = Employee(
            id=existing.id,
            employee_code=existing.employee_code,
            user_id=existing.user_id,
            profile=EmployeeProfile(
                first_name=request.first_name,
                last_name=request.last_name,
                date_of_birth=request.date_of_birth,
                gender=request.gender,
            ),
            contact_info=ContactInformation(
                work_email=Email(request.work_email),
                personal_email=Email(request.personal_email) if request.personal_email else None,
                phone_number=request.phone_number,
            ),
            employment_info=EmploymentInformation(
                department_id=request.department_id,
                manager_id=request.manager_id,
                job_title=request.job_title,
                employment_type=EmploymentType(request.employment_type),
                date_of_joining=request.date_of_joining,
                termination_date=request.termination_date,
            ),
            status=existing.status,
            # Preserved from the existing record — this method rebuilds
            # profile/contact_info/employment_info wholesale from the
            # request (a full-replace update), but Telegram linking is not
            # part of what this endpoint edits at all; dropping these would
            # silently unlink Telegram on every unrelated profile edit.
            telegram_user_id=existing.telegram_user_id,
            telegram_chat_id=existing.telegram_chat_id,
            telegram_username=existing.telegram_username,
            telegram_linked_at=existing.telegram_linked_at,
        )
        updated = self.update(updated_entity)  # validate_update -> uow -> repository.update -> after_update
        return employee_to_response(updated)

    def activate_employee(self, employee_id: uuid.UUID) -> EmployeeResponse:
        existing = self.get_by_id(employee_id)
        activated = existing.activate()  # raises InvalidEmployeeStatusTransitionError if not allowed
        with self._uow:
            saved = self._employees.update(activated)
        self._event_bus.publish(
            EmployeeStatusChanged(employee_id=saved.id, previous_status=existing.status, new_status=saved.status)
        )
        return employee_to_response(saved)

    def deactivate_employee(self, employee_id: uuid.UUID) -> EmployeeResponse:
        existing = self.get_by_id(employee_id)
        deactivated = existing.deactivate()
        with self._uow:
            saved = self._employees.update(deactivated)
        self._event_bus.publish(
            EmployeeStatusChanged(employee_id=saved.id, previous_status=existing.status, new_status=saved.status)
        )
        return employee_to_response(saved)

    # --- BaseService hooks ----------------------------------------------
    def validate_create(self, entity: Employee) -> None:
        if not self._departments.exists(entity.employment_info.department_id):
            raise DepartmentNotFoundError()
        if self._employees.exists_with_work_email(entity.contact_info.work_email):
            raise DuplicateWorkEmailError()
        if entity.user_id is not None and self._employees.get_by_user_id(entity.user_id) is not None:
            raise UserAlreadyLinkedError()

    def validate_update(self, entity: Employee) -> None:
        if not self._departments.exists(entity.employment_info.department_id):
            raise DepartmentNotFoundError()
        holder = self._employees.get_by_work_email(entity.contact_info.work_email)
        if holder is not None and holder.id != entity.id:
            raise DuplicateWorkEmailError()

    def after_create(self, entity: Employee) -> None:
        self._event_bus.publish(
            EmployeeCreated(
                employee_id=entity.id,
                employee_code=entity.employee_code,
                department_id=entity.employment_info.department_id,
            )
        )

    def after_update(self, entity: Employee) -> None:
        self._event_bus.publish(EmployeeUpdated(employee_id=entity.id))
