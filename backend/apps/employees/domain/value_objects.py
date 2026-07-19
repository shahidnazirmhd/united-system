"""Value objects composing the Employee aggregate.

Architectural note (why value objects, not four separate tables/models):
HRMS_Database_Design.md already approved a single `employees.employees`
table (section 3.2) — Employee/Profile/Employment Information/Contact
Information/Status are not four independent lifecycles, they're always
created and updated together as one row. That is precisely when DDD calls
for value objects grouped inside one aggregate root, not separate entities:
each of these validates and is compared by value, has no identity of its
own, and exists only as part of an `Employee`. The Django ORM model backing
all of this (infrastructure/models.py) stays a single flat table matching
what was already approved; `infrastructure/repositories.py`'s
`_to_entity`/`_to_record_kwargs` do the flattening/nesting translation, the
same translation-boundary pattern Identity already established for its
Email value object.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date

from apps.employees.domain.enums import EmploymentType
from shared_kernel.domain.validators import validate_max_length, validate_not_blank
from shared_kernel.domain.value_objects import Email


@dataclass(frozen=True)
class EmployeeProfile:
    """Personal identity fields — the "who" of an employee, independent of
    where they work or how to reach them."""

    first_name: str
    last_name: str
    date_of_birth: date | None = None
    # Open text, not a constrained enum — HRMS_Database_Design.md section
    # 6.3 explicitly calls this out: self-reported personal data where a
    # fixed list would either be incomplete or force a bad fit.
    gender: str | None = None

    def __post_init__(self) -> None:
        validate_not_blank(self.first_name, field_name="first_name")
        validate_max_length(self.first_name, 100, field_name="first_name")
        validate_not_blank(self.last_name, field_name="last_name")
        validate_max_length(self.last_name, 100, field_name="last_name")

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


@dataclass(frozen=True)
class ContactInformation:
    """How to reach an employee. `work_email` is required and unique
    (HRMS_Database_Design.md: UNIQUE, generated/assigned at hire);
    `personal_email` and `phone_number` are optional.
    """

    work_email: Email
    personal_email: Email | None = None
    phone_number: str | None = None

    def __post_init__(self) -> None:
        if self.phone_number is not None:
            validate_max_length(self.phone_number, 20, field_name="phone_number")


@dataclass(frozen=True)
class EmploymentInformation:
    """Where an employee sits structurally and the facts of their
    employment. `department_id`/`manager_id` are plain UUIDs referencing
    `apps.employees.domain.entities.Department` — real foreign keys at the
    ORM/database level (same schema, unlike cross-module references), but
    the domain layer still only ever holds an id, never a nested Department
    object, to avoid the aggregate silently growing to include another
    aggregate root's full data.
    """

    department_id: uuid.UUID
    job_title: str
    employment_type: EmploymentType
    date_of_joining: date
    manager_id: uuid.UUID | None = None
    termination_date: date | None = None

    def __post_init__(self) -> None:
        validate_not_blank(self.job_title, field_name="job_title")
        validate_max_length(self.job_title, 150, field_name="job_title")
        if self.termination_date is not None and self.termination_date < self.date_of_joining:
            raise ValueError("termination_date must not be before date_of_joining")
