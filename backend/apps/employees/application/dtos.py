"""Input/output DTOs for Employee application services.

Interface-layer serializers (interface/serializers.py) convert HTTP
request/response JSON to/from these — services never see a DRF Request or
Response object, only these plain dataclasses. Matches Identity's
application/dtos.py convention exactly.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class CreateEmployeeRequest:
    first_name: str
    last_name: str
    work_email: str
    department_id: uuid.UUID
    job_title: str
    employment_type: str
    date_of_joining: date
    user_id: uuid.UUID | None = None
    personal_email: str | None = None
    phone_number: str | None = None
    date_of_birth: date | None = None
    gender: str | None = None
    manager_id: uuid.UUID | None = None
    created_by: uuid.UUID | None = None


@dataclass(frozen=True)
class UpdateEmployeeRequest:
    employee_id: uuid.UUID
    first_name: str
    last_name: str
    work_email: str
    department_id: uuid.UUID
    job_title: str
    employment_type: str
    date_of_joining: date
    personal_email: str | None = None
    phone_number: str | None = None
    date_of_birth: date | None = None
    gender: str | None = None
    manager_id: uuid.UUID | None = None
    termination_date: date | None = None
    updated_by: uuid.UUID | None = None


@dataclass(frozen=True)
class EmployeeResponse:
    id: uuid.UUID
    employee_code: str
    user_id: uuid.UUID | None
    first_name: str
    last_name: str
    full_name: str
    date_of_birth: date | None
    gender: str | None
    work_email: str
    personal_email: str | None
    phone_number: str | None
    department_id: uuid.UUID
    manager_id: uuid.UUID | None
    job_title: str
    employment_type: str
    date_of_joining: date
    termination_date: date | None
    status: str
    # Resolved only on single-record reads (get_by_id / get_my_profile) —
    # see EmployeeQueryService's docstring for why list/search leave these
    # null rather than resolving them per-row (N+1 avoidance). A field
    # that's "unavailable" per Phase 7's own brief ("If a field is
    # unavailable, display a friendly placeholder") is exactly this shape:
    # present in the DTO, sometimes null, formatter's job to placeholder it.
    department_name: str | None = None
    manager_name: str | None = None
    # Employee & Telegram Authentication refactor: whether/how this employee
    # is linked to Telegram, surfaced on every EmployeeResponse (not just
    # Gateway-facing reads) so a manage_employees-holding HR admin can see
    # link status from the ordinary employee-detail view too.
    is_linked_to_telegram: bool = False
    telegram_username: str | None = None
    telegram_linked_at: datetime | None = None


@dataclass(frozen=True)
class EmployeeListQuery:
    department_id: uuid.UUID | None = None
    status: str | None = None
    employment_type: str | None = None
    search: str | None = None
    ordering: tuple[str, ...] = ()
    page: int = 1
    page_size: int = 25


# --- Telegram linking (Employee & Telegram Authentication refactor) ------
# Moved/redesigned from apps/identity/application/dtos.py's removed
# RequestTelegramLinkRequest/VerifyTelegramLinkRequest/
# TelegramLinkStatusResponse — keyed by employee_code/telegram_user_id, not
# user_id, and with no token pair in the verify response (there is no JWT
# to issue; verification just returns the now-linked EmployeeResponse).


@dataclass(frozen=True)
class RequestEmployeeTelegramLinkRequest:
    employee_code: str
    telegram_user_id: int
    chat_id: int
    telegram_username: str | None = None


@dataclass(frozen=True)
class VerifyEmployeeTelegramLinkRequest:
    telegram_user_id: int
    chat_id: int
    otp: str
    telegram_username: str | None = None


@dataclass(frozen=True)
class EmployeeTelegramLinkStatusResponse:
    is_linked: bool
    telegram_username: str | None
    linked_at: datetime | None
