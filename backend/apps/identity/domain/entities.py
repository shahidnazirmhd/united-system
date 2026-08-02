"""Domain entities for Identity: User, Role, Permission.

Plain Python, no Django. The Django ORM models that persist these
(infrastructure/models.py) are a separate, deliberately distinct set of
classes — see this phase's delivery notes on why. Nothing in this file
knows how a User is stored, only what a User *is*.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from shared_kernel.domain.base_entity import Entity
from apps.identity.domain.value_objects import Email


@dataclass(kw_only=True)
class Permission(Entity):
    code: str
    description: str = ""
    module: str = "identity"


@dataclass(kw_only=True)
class Role(Entity):
    name: str
    description: str = ""
    is_system_role: bool = False
    permission_codes: frozenset[str] = field(default_factory=frozenset)

    def has_permission(self, code: str) -> bool:
        return code in self.permission_codes


@dataclass(kw_only=True)
class User(Entity):
    email: Email
    password_hash: str
    is_active: bool = True
    employee_id: uuid.UUID | None = None
    last_login_at: datetime | None = None
    # Any token issued before this timestamp is treated as invalid, even if
    # its own expiry hasn't passed yet — this is what lets a password reset
    # (or a future admin-triggered "log out everywhere") invalidate every
    # session without needing to individually track and blocklist every
    # refresh token ever issued to this user, which we have no way to
    # enumerate. Checked in both the authentication class (access tokens)
    # and RefreshAccessTokenUseCase (refresh tokens).
    password_changed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    roles: tuple[Role, ...] = field(default_factory=tuple)

    @property
    def role_names(self) -> frozenset[str]:
        return frozenset(role.name for role in self.roles)

    @property
    def permission_codes(self) -> frozenset[str]:
        codes: set[str] = set()
        for role in self.roles:
            codes.update(role.permission_codes)
        return frozenset(codes)

    def has_role(self, role_name: str) -> bool:
        return role_name in self.role_names

    def has_permission(self, permission_code: str) -> bool:
        return permission_code in self.permission_codes

    def activate(self) -> "User":
        """No transition restrictions (unlike Employee's status machine) —
        a User is simply active or not. Deactivation already takes effect
        immediately with no extra token-revocation step needed: `is_active`
        is checked fresh on every authenticated request (see
        IDENTITY_API.md's architecture notes), so re-activating just as
        immediately restores access."""
        return self._with_active(True)

    def deactivate(self) -> "User":
        return self._with_active(False)

    def with_profile(self, *, email: Email) -> "User":
        """Phase 12 admin edit (UpdateUserUseCase) — deliberately excludes
        password_hash (the reset-password flow's job, not edit's) and roles
        (already has its own assign/revoke endpoints), matching Employee's
        UpdateEmployeeSerializer keeping status/telegram fields out of its
        own full-replace update for the identical reason."""
        return User(
            id=self.id,
            email=email,
            password_hash=self.password_hash,
            is_active=self.is_active,
            employee_id=self.employee_id,
            last_login_at=self.last_login_at,
            password_changed_at=self.password_changed_at,
            roles=self.roles,
        )

    def with_employee(self, *, employee_id: uuid.UUID) -> "User":
        """Phase 12 bugfix: the reciprocal half of `Employee.user_id`.
        Called only from `interface/event_handlers.py`'s subscribers to
        `apps.employees`'s `EmployeeCreated`/`EmployeeLinkedToUser` events —
        never from a directly-callable endpoint, since Employee owns the
        decision of *which* employee links to a user; Identity only ever
        records the fact once told. See this module's own `__init__.py`
        docstring for why these are two independent, non-FK fields kept in
        sync via events rather than one owning the other."""
        return User(
            id=self.id,
            email=self.email,
            password_hash=self.password_hash,
            is_active=self.is_active,
            employee_id=employee_id,
            last_login_at=self.last_login_at,
            password_changed_at=self.password_changed_at,
            roles=self.roles,
        )

    def _with_active(self, is_active: bool) -> "User":
        return User(
            id=self.id,
            email=self.email,
            password_hash=self.password_hash,
            is_active=is_active,
            employee_id=self.employee_id,
            last_login_at=self.last_login_at,
            password_changed_at=self.password_changed_at,
            roles=self.roles,
        )


# TelegramAccount/TelegramLinkToken (Phase 7) removed — Telegram linking is
# no longer an Identity concept at all. Employees are never issued a
# `User` account or a JWT for Telegram access; the equivalent entities now
# live in apps/employees/domain/entities.py (Employee's own telegram_* fields
# and the new EmployeeLinkToken), keyed by employee_id, not user_id. See this
# refactor's delivery notes for the full reasoning.


@dataclass(kw_only=True)
class PasswordResetToken(Entity):
    """A single-use, time-limited credential for resetting a password.

    `token_hash` only ever holds a SHA-256 digest — the raw token is never
    persisted (see application/use_cases/request_password_reset.py). This is
    a real domain entity, not just a persistence detail, because "has this
    token already been used or expired" is a business rule
    (ResetPasswordUseCase enforces it), not a database concern.
    """

    user_id: uuid.UUID
    token_hash: str
    expires_at: datetime
    used_at: datetime | None = None

    def is_valid(self, *, now: datetime) -> bool:
        return self.used_at is None and now < self.expires_at
