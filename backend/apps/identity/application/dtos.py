"""Input/output DTOs for Identity use cases.

Interface-layer serializers (interface/serializers.py) convert HTTP
request/response JSON to/from these — use cases never see a DRF Request or
Response object, only these plain dataclasses.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field


@dataclass(frozen=True)
class LoginRequest:
    email: str
    password: str
    source: str = "web"  # "web" | "telegram" | "api"


@dataclass(frozen=True)
class TokenPairResponse:
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int


@dataclass(frozen=True)
class RefreshRequest:
    refresh_token: str


@dataclass(frozen=True)
class LogoutRequest:
    refresh_token: str
    access_token_jti: str | None = None


@dataclass(frozen=True)
class RoleSummary:
    id: uuid.UUID
    name: str


@dataclass(frozen=True)
class UserSummaryResponse:
    id: uuid.UUID
    email: str
    is_active: bool
    employee_id: uuid.UUID | None
    roles: tuple[RoleSummary, ...]
    permission_codes: frozenset[str]


@dataclass(frozen=True)
class CreateUserRequest:
    email: str
    password: str
    created_by: uuid.UUID | None = None


@dataclass(frozen=True)
class UserListQuery:
    """Phase 12 (User Management) — mirrors
    `apps.employees.application.dtos.EmployeeListQuery`'s shape exactly."""

    is_active: bool | None = None
    search: str | None = None
    ordering: tuple[str, ...] = ()
    page: int = 1
    page_size: int = 25


@dataclass(frozen=True)
class UpdateUserRequest:
    """Phase 12 admin edit. Deliberately excludes password (the reset flow's
    job) and roles (already has assign/revoke endpoints) and is_active
    (its own activate/deactivate actions) — matching
    `apps.employees.application.dtos.UpdateEmployeeRequest` keeping
    status/telegram fields out of its own full-replace update for the
    identical reason. `is_system_account` (Phase 12) was removed after being
    found to have no functional effect anywhere in the system — see
    migration 0005_remove_is_system_account's docstring."""

    user_id: uuid.UUID
    email: str
    updated_by: uuid.UUID | None = None


@dataclass(frozen=True)
class CreateRoleRequest:
    name: str
    description: str = ""
    permission_codes: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class RoleResponse:
    id: uuid.UUID
    name: str
    description: str
    is_system_role: bool
    permission_codes: frozenset[str]


@dataclass(frozen=True)
class UpdateRoleRequest:
    """Full-replace update of a role's name/description/permission set —
    backs PATCH /auth/roles/{id}/. `permission_codes` is the *complete*
    target set (mirrors CreateRoleRequest's own all-or-nothing shape, not
    an add/remove diff) — the caller (Role Management UI) always sends every
    checked permission, not just what changed, which is simpler for both
    ends to reason about than a partial patch. Deliberately has no
    `is_system_role` field — whether a role is a system role is decided once,
    at creation (always False for anything created through this API; only
    migration 0002/0006 ever set it True), never editable afterwards."""

    role_id: uuid.UUID
    name: str
    description: str = ""
    permission_codes: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class DeleteRoleRequest:
    role_id: uuid.UUID


@dataclass(frozen=True)
class PermissionResponse:
    id: uuid.UUID
    code: str
    description: str
    module: str


@dataclass(frozen=True)
class AssignRoleRequest:
    user_id: uuid.UUID
    role_id: uuid.UUID
    assigned_by: uuid.UUID | None = None


@dataclass(frozen=True)
class RevokeRoleRequest:
    user_id: uuid.UUID
    role_id: uuid.UUID


@dataclass(frozen=True)
class RequestPasswordResetRequest:
    email: str


@dataclass(frozen=True)
class ConfirmPasswordResetRequest:
    token: str
    new_password: str


# RequestTelegramLinkRequest/VerifyTelegramLinkRequest/
# TelegramLinkStatusResponse (Phase 7) moved to
# apps/employees/application/dtos.py — see this refactor's delivery notes.
