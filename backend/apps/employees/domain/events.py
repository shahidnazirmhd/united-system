"""Domain events published by the Employee module.

Future modules (Leave, Attendance, Payroll, ...) will subscribe to
`EmployeeCreated`/`EmployeeStatusChanged` once they exist — e.g. Leave
provisioning an initial leave balance row the moment an employee is
created. See shared_kernel/infrastructure/event_bus_impl.py for why that
subscription doesn't need to exist yet for these events to be published now.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from apps.employees.domain.enums import EmployeeStatus
from shared_kernel.domain.domain_event import DomainEvent


@dataclass(frozen=True, kw_only=True)
class EmployeeCreated(DomainEvent):
    employee_id: uuid.UUID
    employee_code: str
    department_id: uuid.UUID
    # Phase 12 bugfix: carries the linked user_id (if any was set at
    # creation time) so apps.identity's subscriber can set its own
    # User.employee_id reciprocal field — see EmployeeLinkedToUser's
    # docstring below for why this is a plain event payload field rather
    # than Identity reaching back into Employees to look it up.
    user_id: uuid.UUID | None = None


@dataclass(frozen=True, kw_only=True)
class EmployeeUpdated(DomainEvent):
    employee_id: uuid.UUID


@dataclass(frozen=True, kw_only=True)
class EmployeeLinkedToUser(DomainEvent):
    """Phase 12 bugfix: published by `EmployeeCommandService.link_user`
    specifically (in addition to the generic `EmployeeUpdated`), so
    `apps.identity` can react to *this* employee-to-user link without
    subscribing to every unrelated `EmployeeUpdated` (a regular profile
    edit never changes `user_id` — see `update_employee`'s docstring).

    This event, plus `EmployeeCreated.user_id` above, are the two places
    `Employee.user_id` can ever become non-null; apps.identity's
    subscriber (apps/identity/interface/event_handlers.py) reacts to both
    the same way: set `User.employee_id = employee_id` for the given
    `user_id`. Identity intentionally never queries Employees directly to
    resolve this — see apps/identity/application/ports.py's note on why
    that cross-module lookup was removed — so Employees must push this
    fact to Identity instead of Identity pulling it.
    """

    employee_id: uuid.UUID
    user_id: uuid.UUID


@dataclass(frozen=True, kw_only=True)
class EmployeeStatusChanged(DomainEvent):
    employee_id: uuid.UUID
    previous_status: EmployeeStatus
    new_status: EmployeeStatus


# --- Telegram linking (Employee & Telegram Authentication refactor) ------
# Moved from apps/identity/domain/events.py (TelegramLinkRequested/
# TelegramAccountLinked/TelegramAccountUnlinked) — Telegram linking is
# entirely an Employee concern now, keyed by employee_id, never user_id.


@dataclass(frozen=True, kw_only=True)
class EmployeeTelegramLinkRequested(DomainEvent):
    employee_id: uuid.UUID
    telegram_user_id: int


@dataclass(frozen=True, kw_only=True)
class EmployeeTelegramLinked(DomainEvent):
    employee_id: uuid.UUID
    telegram_user_id: int


@dataclass(frozen=True, kw_only=True)
class EmployeeTelegramUnlinked(DomainEvent):
    employee_id: uuid.UUID
