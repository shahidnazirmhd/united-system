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
from shared_kernel.domain.repository import PageResult, QueryParams


class UserRepository(ABC):
    @abstractmethod
    def get_by_id(self, user_id: uuid.UUID) -> User | None:
        raise NotImplementedError

    @abstractmethod
    def get_by_employee_id(self, employee_id: uuid.UUID) -> User | None:
        """The user account linked to `employee_id`, if any — `User.employee_id`
        is the reverse of `apps.employees`'s own `Employee.user_id`, both
        sides kept in sync at link time. Added for
        `GetPermissionCodesForEmployeeUseCase` (Approval Engine's
        permission-based approval steps), which needs "what can this
        employee do" without ever going through Employees first."""
        raise NotImplementedError

    @abstractmethod
    def get_by_email(self, email: Email) -> User | None:
        raise NotImplementedError

    @abstractmethod
    def list(self, query: QueryParams) -> PageResult[User]:
        """Phase 12 (User Management). Reuses the same `QueryParams`/
        `PageResult` vocabulary `shared_kernel.domain.repository.BaseRepository`
        standardizes for every other module's list endpoint — this class
        doesn't formally inherit `BaseRepository` (see this file's module
        docstring on why Identity's repositories stay hand-written), but
        there's no reason to invent a second pagination shape when this one
        already fits."""
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
        """Insert a brand-new role (CreateRoleUseCase). Grants
        `permission_codes` additively — correct for a fresh role with no
        prior grants to remove. `update()` below is the edit-time
        counterpart, which fully replaces the grant set instead."""
        raise NotImplementedError

    @abstractmethod
    def update(self, role: Role, permission_codes: frozenset[str]) -> Role:
        """Role & Permission Management phase (UpdateRoleUseCase). Unlike
        `save()`, this fully replaces the role's permission grants to match
        `permission_codes` exactly — revoking any grant not in the set, not
        just adding new ones — because an edit's `permission_codes` is
        always the complete target state (see UpdateRoleRequest's
        docstring), not an incremental add list."""
        raise NotImplementedError

    @abstractmethod
    def delete(self, role_id: uuid.UUID) -> None:
        """Role & Permission Management phase (DeleteRoleUseCase). Callers
        must have already checked `is_system_role`/`is_assigned_to_any_user`
        — this method itself performs no business-rule checks, matching
        every other repository method in this module (rule enforcement is
        the use case's job, persistence is this layer's)."""
        raise NotImplementedError

    @abstractmethod
    def is_assigned_to_any_user(self, role_id: uuid.UUID) -> bool:
        """Role & Permission Management phase — backs DeleteRoleUseCase's
        RoleInUseError guard."""
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
