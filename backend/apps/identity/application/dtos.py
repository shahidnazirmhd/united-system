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
    is_system_account: bool
    employee_id: uuid.UUID | None
    roles: tuple[RoleSummary, ...]
    permission_codes: frozenset[str]


@dataclass(frozen=True)
class CreateUserRequest:
    email: str
    password: str
    is_system_account: bool = False
    created_by: uuid.UUID | None = None


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
