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
    last_working_date: date | None = None  # round 15 item 9 — renamed from termination_date
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
    last_working_date: date | None  # round 15 item 9 — renamed from termination_date
    status: str
    # Resolved only on single-record reads (get_by_id / get_my_profile) —
    # see EmployeeQueryService's docstring for why list/search leave these
    # null rather than resolving them per-row (N+1 avoidance). A field
    # that's "unavailable" per Phase 7's own brief ("If a field is
    # unavailable, display a friendly placeholder") is exactly this shape:
    # present in the DTO, sometimes null, formatter's job to placeholder it.
    department_name: str | None = None
    manager_name: str | None = None
    # Phase 12 bugfix: resolved only where user_id is set, and only on
    # single-record reads/writes — same N+1-avoidance shape as
    # department_name/manager_name above (list/search leave this None
    # unconditionally). Backs the Employee Details page's "linked user
    # account" requirement.
    linked_user_email: str | None = None
    # Employee & Telegram Authentication refactor: whether/how this employee
    # is linked to Telegram, surfaced on every EmployeeResponse (not just
    # Gateway-facing reads) so a manage_employees-holding HR admin can see
    # link status from the ordinary employee-detail view too.
    is_linked_to_telegram: bool = False
    telegram_username: str | None = None
    telegram_linked_at: datetime | None = None
    # Approval Engine (Phase 9): the raw Telegram chat id needed to push an
    # unsolicited bot message (an approval notification) to this employee —
    # distinct from `telegram_username` (display only) and not surfaced by
    # any existing serializer (see interface/serializers.py, unchanged);
    # only apps.approvals's own EmployeeLookupPort adapter reads this field.
    telegram_chat_id: int | None = None
    # Round 14 item 8 — see domain/enums.py EmployeeCurrentStatus's
    # docstring for why this is separate from `status` above.
    current_status: str = "not_joined"
    status_before_leave: str | None = None
    # Round 14 item 6 — mirrors `Employee.is_eligible_for_leave` exactly
    # (see that property's docstring), surfaced here so
    # `apps.leave`'s own EmployeeLookupPort adapter never needs to
    # duplicate the NOT_JOINED/TERMINATED/RESIGNED rule itself.
    is_eligible_for_leave: bool = False


@dataclass(frozen=True)
class UpdateEmployeeCurrentStatusRequest:
    """Round 14 item 8 — HR/Admin manual Current Status update. Deliberately
    NOT part of `UpdateEmployeeRequest`'s full-replace update: this is a
    guarded state transition (see `Employee.update_current_status_manually`),
    not a plain field edit, matching how `activate_employee`/
    `deactivate_employee` already have their own dedicated request shape
    (no request DTO at all, just an id) rather than living in the general
    update."""

    employee_id: uuid.UUID
    current_status: str
    updated_by: uuid.UUID | None = None


@dataclass(frozen=True)
class CreateDepartmentRequest:
    name: str
    code: str
    parent_department_id: uuid.UUID | None = None
    head_employee_id: uuid.UUID | None = None
    created_by: uuid.UUID | None = None


@dataclass(frozen=True)
class UpdateDepartmentRequest:
    department_id: uuid.UUID
    name: str
    code: str
    parent_department_id: uuid.UUID | None = None
    head_employee_id: uuid.UUID | None = None
    is_active: bool = True
    updated_by: uuid.UUID | None = None


@dataclass(frozen=True)
class DepartmentResponse:
    id: uuid.UUID
    name: str
    code: str
    parent_department_id: uuid.UUID | None
    head_employee_id: uuid.UUID | None
    is_active: bool
    # Resolved only where the query service does the extra lookup — same
    # "sometimes null, formatter's job to placeholder it" shape as
    # EmployeeResponse.department_name/manager_name.
    parent_department_name: str | None = None
    head_employee_name: str | None = None


@dataclass(frozen=True)
class DepartmentListQuery:
    is_active: bool | None = None
    search: str | None = None
    ordering: tuple[str, ...] = ()
    page: int = 1
    page_size: int = 25


@dataclass(frozen=True)
class LinkUserToEmployeeRequest:
    """Phase 12 (User Management): links an *existing* employee to an
    *existing* user, after the fact — distinct from `user_id` at Create
    time (CreateEmployeeRequest) and deliberately not part of
    UpdateEmployeeRequest's full-replace update (EMPLOYEE_API.md's PATCH
    doc already says user_id is excluded there). See
    EmployeeCommandService.link_user."""

    employee_id: uuid.UUID
    user_id: uuid.UUID
    updated_by: uuid.UUID | None = None


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
