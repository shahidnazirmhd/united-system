"""Grants a role to a user."""
from __future__ import annotations

from apps.identity.application.dtos import AssignRoleRequest
from apps.identity.domain.events import RoleAssignedToUser
from apps.identity.domain.exceptions import (
    RoleAlreadyAssignedError,
    RoleNotFoundError,
    UserNotFoundError,
)
from apps.identity.domain.repositories import RoleRepository, UserRepository
from shared_kernel.application.base_use_case import UseCase
from shared_kernel.application.event_bus import EventBus
from shared_kernel.application.unit_of_work import UnitOfWork


class AssignRoleToUserUseCase(UseCase[AssignRoleRequest, None]):
    def __init__(
        self,
        user_repository: UserRepository,
        role_repository: RoleRepository,
        unit_of_work: UnitOfWork,
        event_bus: EventBus,
    ) -> None:
        self._users = user_repository
        self._roles = role_repository
        self._uow = unit_of_work
        self._event_bus = event_bus

    def execute(self, request: AssignRoleRequest) -> None:
        if self._users.get_by_id(request.user_id) is None:
            raise UserNotFoundError()
        if self._roles.get_by_id(request.role_id) is None:
            raise RoleNotFoundError()
        if self._users.has_role(request.user_id, request.role_id):
            raise RoleAlreadyAssignedError()

        with self._uow:
            self._users.assign_role(request.user_id, request.role_id, request.assigned_by)

        self._event_bus.publish(
            RoleAssignedToUser(
                user_id=request.user_id,
                role_id=request.role_id,
                assigned_by=request.assigned_by,
            )
        )
