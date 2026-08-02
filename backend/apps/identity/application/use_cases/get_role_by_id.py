"""Returns a single role by id — backs GET /auth/roles/{id}/ (Role &
Permission Management phase). Mirrors GetUserByIdUseCase's shape exactly.
"""
from __future__ import annotations

import uuid

from apps.identity.application.dtos import RoleResponse
from apps.identity.application.mappers import role_to_response
from apps.identity.domain.exceptions import RoleNotFoundError
from apps.identity.domain.repositories import RoleRepository
from shared_kernel.application.base_use_case import UseCase


class GetRoleByIdUseCase(UseCase[uuid.UUID, RoleResponse]):
    def __init__(self, role_repository: RoleRepository) -> None:
        self._roles = role_repository

    def execute(self, request: uuid.UUID) -> RoleResponse:
        role = self._roles.get_by_id(request)
        if role is None:
            raise RoleNotFoundError()
        return role_to_response(role)
