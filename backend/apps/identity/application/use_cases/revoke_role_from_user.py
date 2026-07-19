"""Removes a role from a user."""
from __future__ import annotations

from apps.identity.application.dtos import RevokeRoleRequest
from apps.identity.domain.events import RoleRevokedFromUser
from apps.identity.domain.exceptions import RoleNotFoundError
from apps.identity.domain.repositories import UserRepository
from shared_kernel.application.base_use_case import UseCase
from shared_kernel.application.event_bus import EventBus
from shared_kernel.application.unit_of_work import UnitOfWork


class RevokeRoleFromUserUseCase(UseCase[RevokeRoleRequest, None]):
    def __init__(
        self,
        user_repository: UserRepository,
        unit_of_work: UnitOfWork,
        event_bus: EventBus,
    ) -> None:
        self._users = user_repository
        self._uow = unit_of_work
        self._event_bus = event_bus

    def execute(self, request: RevokeRoleRequest) -> None:
        if not self._users.has_role(request.user_id, request.role_id):
            raise RoleNotFoundError("This user does not hold this role.")

        with self._uow:
            self._users.revoke_role(request.user_id, request.role_id)

        self._event_bus.publish(
            RoleRevokedFromUser(user_id=request.user_id, role_id=request.role_id, revoked_by=None)
        )
