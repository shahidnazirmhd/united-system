"""Lists every role — backs GET /auth/roles/."""
from __future__ import annotations

from apps.identity.application.dtos import RoleResponse
from apps.identity.application.mappers import role_to_response
from apps.identity.domain.repositories import RoleRepository
from shared_kernel.application.base_use_case import UseCase


class ListRolesUseCase(UseCase[None, list[RoleResponse]]):
    def __init__(self, role_repository: RoleRepository) -> None:
        self._roles = role_repository

    def execute(self, request: None = None) -> list[RoleResponse]:
        return [role_to_response(role) for role in self._roles.list_all()]
