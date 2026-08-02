"""Entity -> response DTO mapping for Identity, matching
`apps.employees.application.mappers.employee_to_response`'s precedent:
one small pure function instead of every use case repeating the same
field-by-field construction.
"""
from __future__ import annotations

from apps.identity.application.dtos import PermissionResponse, RoleResponse, RoleSummary, UserSummaryResponse
from apps.identity.domain.entities import Permission, Role, User


def user_to_summary_response(user: User) -> UserSummaryResponse:
    return UserSummaryResponse(
        id=user.id,
        email=str(user.email),
        is_active=user.is_active,
        employee_id=user.employee_id,
        roles=tuple(RoleSummary(id=role.id, name=role.name) for role in user.roles),
        permission_codes=user.permission_codes,
    )


def role_to_response(role: Role) -> RoleResponse:
    """Shared by list/create/update-role use cases (Role & Permission
    Management phase) — previously each constructed `RoleResponse` inline;
    consolidated here the moment a second use case needed the identical
    mapping, matching this file's own module docstring precedent."""
    return RoleResponse(
        id=role.id,
        name=role.name,
        description=role.description,
        is_system_role=role.is_system_role,
        permission_codes=role.permission_codes,
    )


def permission_to_response(permission: Permission) -> PermissionResponse:
    return PermissionResponse(
        id=permission.id,
        code=permission.code,
        description=permission.description,
        module=permission.module,
    )
