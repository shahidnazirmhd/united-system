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


@dataclass(frozen=True, kw_only=True)
class EmployeeUpdated(DomainEvent):
    employee_id: uuid.UUID


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
