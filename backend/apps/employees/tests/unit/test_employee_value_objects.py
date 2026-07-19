"""Unit tests for the Employee module's value objects — pure Python, no
Django, no database. Matches Identity's testing convention exactly (see
apps/identity/tests/unit for the precedent)."""
from __future__ import annotations

import uuid
from datetime import date

import pytest

from apps.employees.domain.enums import EmploymentType
from apps.employees.domain.value_objects import ContactInformation, EmployeeProfile, EmploymentInformation
from shared_kernel.api.exceptions import ValidationError
from shared_kernel.domain.value_objects import Email


def test_employee_profile_rejects_blank_first_name() -> None:
    with pytest.raises(ValidationError):
        EmployeeProfile(first_name="  ", last_name="Lovelace")


def test_employee_profile_full_name() -> None:
    profile = EmployeeProfile(first_name="Ada", last_name="Lovelace")
    assert profile.full_name == "Ada Lovelace"


def test_contact_information_normalizes_email_case() -> None:
    contact = ContactInformation(work_email=Email("Ada.Lovelace@Example.com"))
    assert str(contact.work_email) == "ada.lovelace@example.com"


def test_employment_information_rejects_termination_before_joining() -> None:
    with pytest.raises(ValueError):
        EmploymentInformation(
            department_id=uuid.uuid4(),
            job_title="Engineer",
            employment_type=EmploymentType.FULL_TIME,
            date_of_joining=date(2024, 6, 1),
            termination_date=date(2024, 1, 1),
        )


def test_employment_information_allows_termination_on_joining_date() -> None:
    info = EmploymentInformation(
        department_id=uuid.uuid4(),
        job_title="Engineer",
        employment_type=EmploymentType.FULL_TIME,
        date_of_joining=date(2024, 6, 1),
        termination_date=date(2024, 6, 1),
    )
    assert info.termination_date == info.date_of_joining
