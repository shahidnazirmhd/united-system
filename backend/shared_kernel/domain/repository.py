"""Generic repository contract + query/pagination data shapes shared by
every module.

`BaseRepository` is the Repository Pattern boundary already established by
Identity (apps/identity/domain/repositories.py) generalized one level:
Identity's `UserRepository`/`RoleRepository` ABCs are hand-written per
entity because their query methods (get_by_email, assign_role, ...) are
genuinely specific. What *is* uniform across any entity is "get by id, list
with pagination/filter/search/sort, create, update, delete, check
existence" — that shape is captured here once so a future module's own
repository interface can extend this instead of re-declaring it.

`QueryParams`/`PageResult` are framework-independent (no Django import) —
they're the vocabulary a use case/service uses to ask for a page of data and
receive one back, regardless of whether the concrete repository underneath
is Django-ORM-backed (shared_kernel/infrastructure/base_repository.py) or,
in a unit test, an in-memory fake.
"""
from __future__ import annotations

import math
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Generic, TypeVar

from shared_kernel.domain.constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE

EntityT = TypeVar("EntityT")


@dataclass(frozen=True)
class QueryParams:
    """What a caller wants from a `list()` call.

    `filters` is exact-match only (`{"department_id": some_uuid}`) —
    anything requiring an operator (ranges, `__in`, ...) is a custom
    repository method, not something this generic shape tries to express.
    `search` combined with `search_fields` does a case-insensitive
    substring match OR'd across every named field ("list" and "search" as
    distinct-sounding brief items collapse to the same mechanism here: a
    plain list omits `search`, a search request sets it — see
    EMPLOYEE_API.md for how the Employee endpoints use this).
    """

    filters: dict[str, object] = field(default_factory=dict)
    search: str | None = None
    search_fields: tuple[str, ...] = ()
    ordering: tuple[str, ...] = ()
    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE

    def __post_init__(self) -> None:
        if self.page < 1:
            object.__setattr__(self, "page", 1)
        if self.page_size < 1:
            object.__setattr__(self, "page_size", DEFAULT_PAGE_SIZE)
        elif self.page_size > MAX_PAGE_SIZE:
            object.__setattr__(self, "page_size", MAX_PAGE_SIZE)


@dataclass(frozen=True)
class PageResult(Generic[EntityT]):
    items: list[EntityT]
    total_count: int
    page: int
    page_size: int

    @property
    def total_pages(self) -> int:
        if self.page_size <= 0:
            return 0
        return max(1, math.ceil(self.total_count / self.page_size))


class BaseRepository(ABC, Generic[EntityT]):
    """Generic CRUD contract. A module's own repository interface (e.g.
    `apps.employees.domain.repositories.EmployeeRepository`) subclasses
    this and adds whatever entity-specific lookups it needs
    (get_by_employee_code, get_by_work_email, ...) — it is not expected to
    be used unextended.
    """

    @abstractmethod
    def get_by_id(self, entity_id: uuid.UUID) -> EntityT | None:
        raise NotImplementedError

    @abstractmethod
    def list(self, query: QueryParams) -> PageResult[EntityT]:
        raise NotImplementedError

    @abstractmethod
    def create(self, entity: EntityT) -> EntityT:
        raise NotImplementedError

    @abstractmethod
    def update(self, entity: EntityT) -> EntityT:
        raise NotImplementedError

    @abstractmethod
    def delete(self, entity_id: uuid.UUID) -> None:
        raise NotImplementedError

    @abstractmethod
    def exists(self, entity_id: uuid.UUID) -> bool:
        raise NotImplementedError
