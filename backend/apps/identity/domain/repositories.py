"""Repository interfaces for Identity — the Repository Pattern boundary
between the domain/application layers and persistence.

Concrete implementations (infrastructure/repositories.py) are Django
ORM-backed, but nothing above this file knows that. A use case depends only
on these ABCs, never on Django's QuerySet API directly — Dependency
Inversion applied to persistence, matching the pattern used for
UnitOfWork/EventBus in shared_kernel.
"""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import datetime

from apps.identity.domain.entities import PasswordResetToken, Permission, Role, User
from apps.identity.domain.value_objects import Email


class UserRepository(ABC):
    @abstractmethod
    def get_by_id(self, user_id: uuid.UUID) -> User | None:
        raise NotImplementedError

    @abstractmethod
    def get_by_email(self, email: Email) -> User | None:
        raise NotImplementedError

    @abstractmethod
    def save(self, user: User) -> User:
        """Insert or update. Returns the persisted entity (with any
        database-assigned defaults populated)."""
        raise NotImplementedError

    @abstractmethod
    def exists_with_email(self, email: Email) -> bool:
        raise NotImplementedError

    @abstractmethod
    def assign_role(self, user_id: uuid.UUID, role_id: uuid.UUID, assigned_by: uuid.UUID | None) -> None:
        raise NotImplementedError

    @abstractmethod
    def revoke_role(self, user_id: uuid.UUID, role_id: uuid.UUID) -> None:
        raise NotImplementedError

    @abstractmethod
    def has_role(self, user_id: uuid.UUID, role_id: uuid.UUID) -> bool:
        raise NotImplementedError


class RoleRepository(ABC):
    @abstractmethod
    def get_by_id(self, role_id: uuid.UUID) -> Role | None:
        raise NotImplementedError

    @abstractmethod
    def get_by_name(self, name: str) -> Role | None:
        raise NotImplementedError

    @abstractmethod
    def list_all(self) -> list[Role]:
        raise NotImplementedError

    @abstractmethod
    def save(self, role: Role, permission_codes: frozenset[str]) -> Role:
        raise NotImplementedError

    @abstractmethod
    def exists_with_name(self, name: str) -> bool:
        raise NotImplementedError


class PermissionRepository(ABC):
    @abstractmethod
    def list_all(self) -> list[Permission]:
        raise NotImplementedError

    @abstractmethod
    def get_by_codes(self, codes: frozenset[str]) -> list[Permission]:
        raise NotImplementedError


class PasswordResetTokenRepository(ABC):
    @abstractmethod
    def create(self, user_id: uuid.UUID, token_hash: str, expires_at: datetime) -> PasswordResetToken:
        raise NotImplementedError

    @abstractmethod
    def get_by_hash(self, token_hash: str) -> PasswordResetToken | None:
        raise NotImplementedError

    @abstractmethod
    def mark_used(self, token_hash: str, *, used_at: datetime) -> None:
        raise NotImplementedError


# TelegramAccountRepository/TelegramLinkTokenRepository removed — see this
# file's module docstring update note in the refactor delivery notes.
# Equivalent repositories now live in apps/employees/domain/repositories.py,
# keyed by employee_id.
