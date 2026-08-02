"""Edits a role's name/description/permission set — backs PATCH /auth/roles/{id}/.

Deliberately usable on system roles too (only *deletion* is blocked for
those — see DeleteRoleUseCase) — an Admin adding a permission this phase's
identity migration didn't anticipate to the Admin role itself is a normal,
supported operation, not a special case.
"""
from __future__ import annotations

from apps.identity.application.dtos import RoleResponse, UpdateRoleRequest
from apps.identity.application.mappers import role_to_response
from apps.identity.domain.entities import Role
from apps.identity.domain.exceptions import DuplicateRoleNameError, PermissionNotFoundError, RoleNotFoundError
from apps.identity.domain.repositories import PermissionRepository, RoleRepository
from shared_kernel.application.base_use_case import UseCase
from shared_kernel.application.unit_of_work import UnitOfWork


class UpdateRoleUseCase(UseCase[UpdateRoleRequest, RoleResponse]):
    def __init__(
        self,
        role_repository: RoleRepository,
        permission_repository: PermissionRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._roles = role_repository
        self._permissions = permission_repository
        self._uow = unit_of_work

    def execute(self, request: UpdateRoleRequest) -> RoleResponse:
        existing = self._roles.get_by_id(request.role_id)
        if existing is None:
            raise RoleNotFoundError()

        if request.name != existing.name and self._roles.exists_with_name(request.name):
            raise DuplicateRoleNameError()

        if request.permission_codes:
            found = {p.code for p in self._permissions.get_by_codes(request.permission_codes)}
            missing = request.permission_codes - found
            if missing:
                raise PermissionNotFoundError(f"Unknown permission code(s): {', '.join(sorted(missing))}")

        updated = Role(
            id=existing.id,
            name=request.name,
            description=request.description,
            is_system_role=existing.is_system_role,
            permission_codes=existing.permission_codes,
        )

        with self._uow:
            saved = self._roles.update(updated, request.permission_codes)

        return role_to_response(saved)
