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

from apps.employees.application.dtos import (
    CreateEmployeeRequest,
    EmployeeResponse,
    LinkUserToEmployeeRequest,
    UpdateEmployeeCurrentStatusRequest,
    UpdateEmployeeRequest,
)
from apps.employees.application.mappers import employee_to_response
from apps.employees.application.ports import UserLookupPort
from apps.employees.domain.entities import Employee
from apps.employees.domain.enums import EmployeeCurrentStatus, EmploymentType
from apps.employees.domain.events import (
    EmployeeCreated,
    EmployeeLinkedToUser,
    EmployeeStatusChanged,
    EmployeeTelegramUnlinked,
    EmployeeUpdated,
)
from apps.employees.domain.exceptions import (
    DepartmentNotFoundError,
    DuplicateWorkEmailError,
    EmployeeNotFoundError,
    UserAlreadyLinkedError,
    UserNotFoundError,
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
        user_lookup: UserLookupPort | None = None,
    ) -> None:
        super().__init__(repository=employee_repository, unit_of_work=unit_of_work, event_bus=event_bus)
        self._employees = employee_repository
        self._departments = department_repository
        # Optional (default None) so every existing unit test constructing
        # this service with fakes for the other four args keeps working
        # unchanged — only link_user (Phase 12) actually needs this one.
        self._user_lookup = user_lookup

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
                last_working_date=request.last_working_date,  # round 15 item 9
            ),
            status=existing.status,
            # Preserved from the existing record — this method rebuilds
            # profile/contact_info/employment_info wholesale from the
            # request (a full-replace update), but Telegram linking and
            # Current Status are not part of what this endpoint edits at
            # all; dropping them would silently unlink Telegram / reset
            # Current Status to Not Joined on every unrelated profile edit.
            telegram_user_id=existing.telegram_user_id,
            telegram_chat_id=existing.telegram_chat_id,
            telegram_username=existing.telegram_username,
            telegram_linked_at=existing.telegram_linked_at,
            current_status=existing.current_status,
            status_before_leave=existing.status_before_leave,
        )
        updated = self.update(updated_entity)  # validate_update -> uow -> repository.update -> after_update
        return employee_to_response(updated)

    def link_user(self, request: LinkUserToEmployeeRequest) -> EmployeeResponse:
        """Phase 12 (User Management): links an existing employee to an
        existing user after the fact — the only way to do this today is
        `user_id` at Employee creation time; this closes that gap without
        touching update_employee's full-replace semantics (user_id stays
        excluded from UpdateEmployeeSerializer, per EMPLOYEE_API.md)."""
        assert self._user_lookup is not None, (
            "EmployeeCommandService.link_user requires a UserLookupPort — "
            "see interface/dependencies.py's build_employee_command_service."
        )
        existing = self.get_by_id(request.employee_id)  # raises EmployeeNotFoundError

        if not self._user_lookup.user_exists(request.user_id):
            raise UserNotFoundError()

        holder = self._employees.get_by_user_id(request.user_id)
        if holder is not None and holder.id != existing.id:
            raise UserAlreadyLinkedError()

        updated_entity = Employee(
            id=existing.id,
            employee_code=existing.employee_code,
            user_id=request.user_id,
            profile=existing.profile,
            contact_info=existing.contact_info,
            employment_info=existing.employment_info,
            status=existing.status,
            telegram_user_id=existing.telegram_user_id,
            telegram_chat_id=existing.telegram_chat_id,
            telegram_username=existing.telegram_username,
            telegram_linked_at=existing.telegram_linked_at,
            current_status=existing.current_status,
            status_before_leave=existing.status_before_leave,
        )
        with self._uow:
            saved = self._employees.update(updated_entity)
        self._event_bus.publish(EmployeeUpdated(employee_id=saved.id))
        # Bugfix: this is the event apps.identity actually subscribes to for
        # reciprocal User.employee_id sync — EmployeeUpdated alone never
        # carried user_id and a regular profile edit never changes it, so
        # this specific event is the only reliable signal a link just
        # happened. See EmployeeLinkedToUser's docstring.
        self._event_bus.publish(EmployeeLinkedToUser(employee_id=saved.id, user_id=request.user_id))
        return employee_to_response(saved)

    def update_current_status(self, request: UpdateEmployeeCurrentStatusRequest) -> EmployeeResponse:
        """Round 14 item 8 — HR/Admin manual Current Status update. Delegates
        every transition rule to `Employee.update_current_status_manually`
        (raises `InvalidCurrentStatusTransitionError` for anything not
        allowed) — this method's only job is fetch, delegate, persist,
        matching `activate_employee`/`deactivate_employee`'s identical
        shape."""
        existing = self.get_by_id(request.employee_id)
        updated = existing.update_current_status_manually(EmployeeCurrentStatus(request.current_status))
        with self._uow:
            saved = self._employees.update(updated)
        return employee_to_response(saved)

    def enter_leave_status(self, employee_id: uuid.UUID, leave_status: str) -> EmployeeResponse:
        """System-only path (round 14 item 8/6 integration) — called by
        `apps.leave`'s own status-integration adapter, never directly by
        any HTTP endpoint (there is no route for this). See
        `Employee.enter_leave_status`'s docstring for the full transition
        rules; this method's only job is fetch, delegate, persist."""
        existing = self.get_by_id(employee_id)
        updated = existing.enter_leave_status(EmployeeCurrentStatus(leave_status))
        with self._uow:
            saved = self._employees.update(updated)
        return employee_to_response(saved)

    def exit_leave_status(self, employee_id: uuid.UUID) -> EmployeeResponse:
        """System-only path — see `enter_leave_status`'s docstring above."""
        existing = self.get_by_id(employee_id)
        updated = existing.exit_leave_status()
        with self._uow:
            saved = self._employees.update(updated)
        return employee_to_response(saved)

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
        # Round 14 item 7: "When an employee is deactivated, automatically
        # unlink the Telegram account." Done in the same transaction as the
        # status change itself — a deactivation must never leave a
        # still-linked Telegram account behind, even if a caller retries
        # after a partial failure.
        was_linked_to_telegram = deactivated.is_linked_to_telegram
        if was_linked_to_telegram:
            deactivated = deactivated.unlink_telegram()
        with self._uow:
            saved = self._employees.update(deactivated)
        self._event_bus.publish(
            EmployeeStatusChanged(employee_id=saved.id, previous_status=existing.status, new_status=saved.status)
        )
        if was_linked_to_telegram:
            self._event_bus.publish(EmployeeTelegramUnlinked(employee_id=saved.id))
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
                # Bugfix: lets apps.identity sync its own User.employee_id
                # when an employee is created already linked to a user
                # (rather than linked later via link_user) — previously
                # dropped entirely, which is one of the two ways the
                # reported "linked employee not reflected in /auth/me/" bug
                # could happen.
                user_id=entity.user_id,
            )
        )

    def after_update(self, entity: Employee) -> None:
        self._event_bus.publish(EmployeeUpdated(employee_id=entity.id))
