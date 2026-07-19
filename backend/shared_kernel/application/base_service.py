"""Generic CRUD service every future module's application layer can extend.

Identity used one class per use case (LoginUserUseCase, CreateUserUseCase,
...) because its actions are genuinely distinct operations with little
shared shape. A module whose work is mostly "create/read/update this kind
of record, with some validation and a couple of state transitions" — the
Employee module being the first example — benefits from a shared skeleton
instead: `BaseService` supplies get/list/create/update/delete wired to a
`BaseRepository` and a `UnitOfWork`, plus validation hooks a subclass
overrides. This does not replace the `UseCase` pattern (shared_kernel's
`base_use_case.py`) — it's an alternative shape for a different kind of
module; a use case remains the right tool when an action doesn't fit the
CRUD mold (see apps/employees/application/services for how Employee's
activate/deactivate — real state transitions, not CRUD — are still thin,
explicit methods rather than forced into this base).
"""
from __future__ import annotations

import uuid
from typing import Generic, TypeVar

from shared_kernel.api.exceptions import NotFoundError
from shared_kernel.application.event_bus import EventBus
from shared_kernel.application.unit_of_work import UnitOfWork
from shared_kernel.domain.repository import BaseRepository, PageResult, QueryParams

EntityT = TypeVar("EntityT")


class BaseService(Generic[EntityT]):
    #: Raised by `get_by_id` when nothing is found — a subclass whose module
    #: has a more specific "not found" exception (e.g. EmployeeNotFoundError)
    #: overrides this attribute rather than the method.
    not_found_exception: type[NotFoundError] = NotFoundError

    def __init__(
        self,
        repository: BaseRepository[EntityT],
        unit_of_work: UnitOfWork,
        event_bus: EventBus | None = None,
    ) -> None:
        self._repository = repository
        self._uow = unit_of_work
        self._event_bus = event_bus

    def get_by_id(self, entity_id: uuid.UUID) -> EntityT:
        entity = self._repository.get_by_id(entity_id)
        if entity is None:
            raise self.not_found_exception()
        return entity

    def list(self, query: QueryParams) -> PageResult[EntityT]:
        return self._repository.list(query)

    def create(self, entity: EntityT) -> EntityT:
        self.validate_create(entity)
        with self._uow:
            created = self._repository.create(entity)
        self.after_create(created)
        return created

    def update(self, entity: EntityT) -> EntityT:
        self.validate_update(entity)
        with self._uow:
            updated = self._repository.update(entity)
        self.after_update(updated)
        return updated

    def delete(self, entity_id: uuid.UUID) -> None:
        with self._uow:
            self._repository.delete(entity_id)

    # --- Validation/lifecycle hooks -----------------------------------
    # Template Method pattern: no-op by default, so extending behaviour
    # means a subclass overrides one of these (Open/Closed), not editing
    # create()/update() themselves.
    def validate_create(self, entity: EntityT) -> None:
        pass

    def validate_update(self, entity: EntityT) -> None:
        pass

    def after_create(self, entity: EntityT) -> None:
        pass

    def after_update(self, entity: EntityT) -> None:
        pass
