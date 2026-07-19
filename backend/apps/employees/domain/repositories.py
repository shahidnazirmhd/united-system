"""Repository interfaces for Employees — extends shared_kernel's generic
`BaseRepository` (shared_kernel/domain/repository.py) with the
entity-specific lookups a generic CRUD contract can't express, matching
exactly the extension pattern Identity's hand-written repositories already
established (apps/identity/domain/repositories.py), just built on the new
generic base instead of starting from nothing.
"""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import datetime

from apps.employees.domain.entities import Department, Employee, EmployeeLinkToken
from shared_kernel.domain.repository import BaseRepository
from shared_kernel.domain.value_objects import Email


class EmployeeRepository(BaseRepository[Employee]):
    @abstractmethod
    def get_by_employee_code(self, employee_code: str) -> Employee | None:
        raise NotImplementedError

    @abstractmethod
    def get_by_work_email(self, work_email: Email) -> Employee | None:
        raise NotImplementedError

    @abstractmethod
    def get_by_user_id(self, user_id: uuid.UUID) -> Employee | None:
        raise NotImplementedError

    @abstractmethod
    def get_by_telegram_user_id(self, telegram_user_id: int) -> Employee | None:
        """Employee & Telegram Authentication refactor: the lookup the
        Telegram Gateway's every post-linking request resolves through —
        the Telegram user id is, per the refactor's own spec, "the only
        information required to identify the employee in future Telegram
        requests." See interface/views.py's Gateway-facing endpoints."""
        raise NotImplementedError

    @abstractmethod
    def exists_with_telegram_user_id(self, telegram_user_id: int) -> bool:
        raise NotImplementedError

    @abstractmethod
    def exists_with_employee_code(self, employee_code: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def exists_with_work_email(self, work_email: Email) -> bool:
        raise NotImplementedError

    @abstractmethod
    def next_employee_code(self) -> str:
        """Race-safe, monotonically increasing employee code (e.g.
        `EMP-000042`) backed by a real Postgres sequence — see
        infrastructure/sequence.py for why a row-count-based scheme was
        rejected."""
        raise NotImplementedError


class DepartmentRepository(ABC):
    @abstractmethod
    def get_by_id(self, department_id: uuid.UUID) -> Department | None:
        raise NotImplementedError

    @abstractmethod
    def exists(self, department_id: uuid.UUID) -> bool:
        raise NotImplementedError


class EmployeeLinkTokenRepository(ABC):
    """Employee & Telegram Authentication refactor — moved from (removed)
    apps.identity.domain.repositories.TelegramLinkTokenRepository, keyed by
    employee_id instead of user_id.

    Looked up by (telegram_user_id, chat_id) — "the pending link attempt for
    this chat" — not by the OTP's own hash. That distinction matters for the
    brute-force lockout (MAX_OTP_ATTEMPTS in
    application/services/employee_telegram_linking_service.py): a *wrong*
    OTP guess must still resolve to the real pending token so its
    attempt_count can be incremented, which a hash-keyed lookup could never
    do (a wrong guess's hash simply matches no row at all).
    """

    @abstractmethod
    def create(self, token: EmployeeLinkToken) -> EmployeeLinkToken:
        raise NotImplementedError

    @abstractmethod
    def get_pending_by_chat(self, *, telegram_user_id: int, chat_id: int) -> EmployeeLinkToken | None:
        """The most recently created not-yet-used token for this chat,
        regardless of whether it has since expired — callers decide what
        "expired" means (see verify_link), this just finds the row.
        Returns None if no token was ever created for this chat, or if the
        only one(s) that exist are already used."""
        raise NotImplementedError

    @abstractmethod
    def increment_attempt_count(self, token: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def mark_used(self, token: str, *, used_at: datetime) -> None:
        raise NotImplementedError
