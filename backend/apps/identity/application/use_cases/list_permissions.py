"""Lists every registered permission — backs GET /auth/permissions/.

Role & Permission Management phase: the frontend's Role create/edit form
needs the full catalogue of assignable permission codes (grouped by
`module`) to render its permission picker, rather than hardcoding a list
that would go stale the moment a new module seeds its own permissions (see
apps/identity/migrations/0002_seed_system_roles.py's Open/Closed note).
"""
from __future__ import annotations

from apps.identity.application.dtos import PermissionResponse
from apps.identity.application.mappers import permission_to_response
from apps.identity.domain.repositories import PermissionRepository
from shared_kernel.application.base_use_case import UseCase


class ListPermissionsUseCase(UseCase[None, list[PermissionResponse]]):
    def __init__(self, permission_repository: PermissionRepository) -> None:
        self._permissions = permission_repository

    def execute(self, request: None = None) -> list[PermissionResponse]:
        return [permission_to_response(p) for p in self._permissions.list_all()]
