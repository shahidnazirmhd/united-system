"""Django ORM-backed implementations of the Employee repository interfaces.

`DjangoEmployeeRepository` extends shared_kernel's generic
`DjangoBaseRepository` for CRUD/pagination/filter/search/sort, and adds only
the entity-specific lookups (`get_by_employee_code`, `get_by_work_email`,
`get_by_user_id`, `next_employee_code`) that a generic base can't express —
this is where the *Record <-> domain-entity translation boundary Identity
established (apps/identity/infrastructure/repositories.py) lives for
Employees too.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from django.db.models import F

from apps.employees.domain.entities import Department, Employee, EmployeeLinkToken
from apps.employees.domain.enums import EmployeeCurrentStatus, EmployeeStatus, EmploymentType
from apps.employees.domain.repositories import (
    DepartmentRepository,
    EmployeeLinkTokenRepository,
    EmployeeRepository,
)
from apps.employees.domain.value_objects import ContactInformation, EmployeeProfile, EmploymentInformation
from apps.employees.infrastructure.models import DepartmentRecord, EmployeeLinkTokenRecord, EmployeeRecord
from apps.employees.infrastructure.sequence import next_employee_code
from shared_kernel.domain.value_objects import Email
from shared_kernel.infrastructure.base_repository import DjangoBaseRepository


def _employee_to_domain(record: EmployeeRecord) -> Employee:
    return Employee(
        id=record.id,
        employee_code=record.employee_code,
        user_id=record.user_id,
        profile=EmployeeProfile(
            first_name=record.first_name,
            last_name=record.last_name,
            date_of_birth=record.date_of_birth,
            gender=record.gender,
        ),
        contact_info=ContactInformation(
            work_email=Email(record.work_email),
            personal_email=Email(record.personal_email) if record.personal_email else None,
            phone_number=record.phone_number,
        ),
        employment_info=EmploymentInformation(
            department_id=record.department_id,
            manager_id=record.manager_id,
            job_title=record.job_title,
            employment_type=EmploymentType(record.employment_type),
            date_of_joining=record.date_of_joining,
            last_working_date=record.last_working_date,  # round 15 item 9
        ),
        status=EmployeeStatus(record.employment_status),
        telegram_user_id=record.telegram_user_id,
        telegram_chat_id=record.telegram_chat_id,
        telegram_username=record.telegram_username,
        telegram_linked_at=record.telegram_linked_at,
        current_status=EmployeeCurrentStatus(record.current_status),
        status_before_leave=EmployeeCurrentStatus(record.status_before_leave)
        if record.status_before_leave
        else None,
    )


def _department_to_domain(record: DepartmentRecord) -> Department:
    return Department(
        id=record.id,
        name=record.name,
        code=record.code,
        parent_department_id=record.parent_department_id,
        head_employee_id=record.head_employee_id,
        is_active=record.is_active,
    )


class DjangoEmployeeRepository(DjangoBaseRepository[EmployeeRecord, Employee], EmployeeRepository):
    model = EmployeeRecord

    def _to_entity(self, record: EmployeeRecord) -> Employee:
        return _employee_to_domain(record)

    def _to_record_kwargs(self, entity: Employee) -> dict[str, object]:
        return {
            "employee_code": entity.employee_code,
            "user_id": entity.user_id,
            "first_name": entity.profile.first_name,
            "last_name": entity.profile.last_name,
            "date_of_birth": entity.profile.date_of_birth,
            "gender": entity.profile.gender,
            "work_email": str(entity.contact_info.work_email),
            "personal_email": str(entity.contact_info.personal_email)
            if entity.contact_info.personal_email
            else None,
            "phone_number": entity.contact_info.phone_number,
            "department_id": entity.employment_info.department_id,
            "manager_id": entity.employment_info.manager_id,
            "job_title": entity.employment_info.job_title,
            "employment_type": entity.employment_info.employment_type.value,
            "date_of_joining": entity.employment_info.date_of_joining,
            "last_working_date": entity.employment_info.last_working_date,  # round 15 item 9
            "employment_status": entity.status.value,
            "telegram_user_id": entity.telegram_user_id,
            "telegram_chat_id": entity.telegram_chat_id,
            "telegram_username": entity.telegram_username,
            "telegram_linked_at": entity.telegram_linked_at,
            "current_status": entity.current_status.value,
            "status_before_leave": entity.status_before_leave.value if entity.status_before_leave else None,
        }

    def get_by_employee_code(self, employee_code: str) -> Employee | None:
        record = self._base_queryset().filter(employee_code=employee_code).first()
        return self._to_entity(record) if record is not None else None

    def get_by_work_email(self, work_email: Email) -> Employee | None:
        record = self._base_queryset().filter(work_email=str(work_email)).first()
        return self._to_entity(record) if record is not None else None

    def get_by_user_id(self, user_id: uuid.UUID) -> Employee | None:
        record = self._base_queryset().filter(user_id=user_id).first()
        return self._to_entity(record) if record is not None else None

    def get_by_telegram_user_id(self, telegram_user_id: int) -> Employee | None:
        record = self._base_queryset().filter(telegram_user_id=telegram_user_id).first()
        return self._to_entity(record) if record is not None else None

    def exists_with_telegram_user_id(self, telegram_user_id: int) -> bool:
        return self.model.objects.filter(telegram_user_id=telegram_user_id).exists()

    def exists_with_employee_code(self, employee_code: str) -> bool:
        return self.model.objects.filter(employee_code=employee_code).exists()

    def exists_with_work_email(self, work_email: Email) -> bool:
        return self.model.objects.filter(work_email=str(work_email)).exists()

    def next_employee_code(self) -> str:
        return next_employee_code()


class DjangoDepartmentRepository(DjangoBaseRepository[DepartmentRecord, Department], DepartmentRepository):
    """Phase 12 (Department CRUD) — now built on the same generic
    `DjangoBaseRepository` `DjangoEmployeeRepository` uses above, instead of
    the two hand-written lookup methods this class started with. Base
    ordering `(DjangoBaseRepository[...], DepartmentRepository)` matches
    `DjangoEmployeeRepository`'s own MRO exactly — see that base class's
    docstring for why the order must agree across every module."""

    model = DepartmentRecord

    def _to_entity(self, record: DepartmentRecord) -> Department:
        return _department_to_domain(record)

    def _to_record_kwargs(self, entity: Department) -> dict[str, object]:
        return {
            "name": entity.name,
            "code": entity.code,
            "parent_department_id": entity.parent_department_id,
            "head_employee_id": entity.head_employee_id,
            "is_active": entity.is_active,
        }

    def exists_with_code(self, code: str) -> bool:
        return self.model.objects.filter(code=code).exists()

    def get_by_ids(self, ids: frozenset[uuid.UUID]) -> list[Department]:
        if not ids:
            return []
        return [self._to_entity(record) for record in self.model.objects.filter(id__in=ids)]


def _employee_link_token_to_domain(record: EmployeeLinkTokenRecord) -> EmployeeLinkToken:
    return EmployeeLinkToken(
        id=record.id,
        employee_id=record.employee_id,
        token=record.token,
        telegram_user_id=record.telegram_user_id,
        chat_id=record.chat_id,
        telegram_username=record.telegram_username,
        expires_at=record.expires_at,
        used_at=record.used_at,
        attempt_count=record.attempt_count,
    )


class DjangoEmployeeLinkTokenRepository(EmployeeLinkTokenRepository):
    def create(self, token: EmployeeLinkToken) -> EmployeeLinkToken:
        record = EmployeeLinkTokenRecord.objects.create(
            id=token.id,
            employee_id=token.employee_id,
            token=token.token,
            telegram_user_id=token.telegram_user_id,
            chat_id=token.chat_id,
            telegram_username=token.telegram_username,
            expires_at=token.expires_at,
        )
        return _employee_link_token_to_domain(record)

    def get_pending_by_chat(self, *, telegram_user_id: int, chat_id: int) -> EmployeeLinkToken | None:
        record = (
            EmployeeLinkTokenRecord.objects.filter(
                telegram_user_id=telegram_user_id, chat_id=chat_id, used_at__isnull=True
            )
            .order_by("-created_at")
            .first()
        )
        return _employee_link_token_to_domain(record) if record is not None else None

    def increment_attempt_count(self, token: str) -> None:
        # F()-expression update, not read-modify-write: two near-simultaneous
        # wrong guesses against the same token must both actually count,
        # not race and silently lose one increment.
        EmployeeLinkTokenRecord.objects.filter(token=token).update(attempt_count=F("attempt_count") + 1)

    def mark_used(self, token: str, *, used_at: datetime) -> None:
        EmployeeLinkTokenRecord.objects.filter(token=token).update(used_at=used_at)
