"""Creates a new role with an initial permission set.

Validates every requested permission code actually exists — silently
ignoring unknown codes would let a typo quietly grant a role fewer
permissions than intended, which is the wrong failure mode for an
authorization system.
"""
from __future__ import annotations

from apps.identity.application.dtos import CreateRoleRequest, RoleResponse
from apps.identity.domain.entities import Role
from apps.identity.domain.exceptions import DuplicateRoleNameError, PermissionNotFoundError
from apps.identity.domain.repositories import PermissionRepository, RoleRepository
from shared_kernel.application.base_use_case import UseCase
from shared_kernel.application.unit_of_work import UnitOfWork
from shared_kernel.infrastructure.uuid7 import generate_uuid7


class CreateRoleUseCase(UseCase[CreateRoleRequest, RoleResponse]):
    def __init__(
        self,
        role_repository: RoleRepository,
        permission_repository: PermissionRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._roles = role_repository
        self._permissions = permission_repository
        self._uow = unit_of_work

    def execute(self, request: CreateRoleRequest) -> RoleResponse:
        if self._roles.exists_with_name(request.name):
            raise DuplicateRoleNameError()

        if request.permission_codes:
            found = {p.code for p in self._permissions.get_by_codes(request.permission_codes)}
            missing = request.permission_codes - found
            if missing:
                raise PermissionNotFoundError(f"Unknown permission code(s): {', '.join(sorted(missing))}")

        role = Role(id=generate_uuid7(), name=request.name, description=request.description)

        with self._uow:
            saved = self._roles.save(role, request.permission_codes)

        return RoleResponse(
            id=saved.id,
            name=saved.name,
            description=saved.description,
            is_system_role=saved.is_system_role,
            permission_codes=saved.permission_codes,
        )
