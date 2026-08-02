"""Deletes a role — backs DELETE /auth/roles/{id}/.

Two guards, in order:
1. System roles (`is_system_role=True` — currently only "Admin", see
   migration 0006_rename_admin_role_and_prune_system_roles.py) can never be
   deleted. Losing the one role every identity.* permission is guaranteed to
   be reachable from would be an unrecoverable lockout.
2. A role still assigned to at least one user cannot be deleted either —
   the caller must revoke it from every holder first. See
   RoleInUseError's docstring for why this isn't just cascaded silently.
"""
from __future__ import annotations

from apps.identity.application.dtos import DeleteRoleRequest
from apps.identity.domain.exceptions import CannotDeleteSystemRoleError, RoleInUseError, RoleNotFoundError
from apps.identity.domain.repositories import RoleRepository
from shared_kernel.application.base_use_case import UseCase
from shared_kernel.application.unit_of_work import UnitOfWork


class DeleteRoleUseCase(UseCase[DeleteRoleRequest, None]):
    def __init__(self, role_repository: RoleRepository, unit_of_work: UnitOfWork) -> None:
        self._roles = role_repository
        self._uow = unit_of_work

    def execute(self, request: DeleteRoleRequest) -> None:
        role = self._roles.get_by_id(request.role_id)
        if role is None:
            raise RoleNotFoundError()

        if role.is_system_role:
            raise CannotDeleteSystemRoleError()

        if self._roles.is_assigned_to_any_user(request.role_id):
            raise RoleInUseError()

        with self._uow:
            self._roles.delete(request.role_id)
