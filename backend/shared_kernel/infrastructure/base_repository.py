"""Generic Django-ORM-backed implementation of `BaseRepository`.

Provides get_by_id/list/create/update/delete/exists once, with real
pagination, filtering, search, and sorting, so a module's own repository
implementation only has to supply two things: which Django model to use,
and the two translation functions between that model and the domain entity
(the same *Record <-> domain-entity translation boundary Identity already
established in apps/identity/infrastructure/repositories.py — this class
doesn't change that pattern, it just removes the boilerplate CRUD/pagination
code every repository was otherwise going to duplicate around it).

Deliberately NOT generic for anything beyond CRUD + list shape: `create`/
`update` here work from a plain dict of ORM field values (subclasses build
that dict from the entity in `_to_record_kwargs`), which is a asymmetric
design point worth calling out — reads (list/get) are fully generic because
their *shape* (paginate, filter, search, sort) is genuinely uniform across
every future module, but this class does not try to guess how to construct
an entity's related rows (e.g. M2M) generically, since that's inherently
entity-specific — a subclass overrides `create`/`update` when it needs that
(see apps/identity's repositories for the equivalent, hand-written version
of this same judgment call, made before this generic base existed).
"""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from django.db import models
from django.db.models import Q

from shared_kernel.domain.repository import PageResult, QueryParams

ModelT = TypeVar("ModelT", bound=models.Model)
EntityT = TypeVar("EntityT")


class DjangoBaseRepository(ABC, Generic[ModelT, EntityT]):
    """Base ordering is `(ABC, Generic[...])`, matching
    `shared_kernel.domain.repository.BaseRepository` and
    `shared_kernel.application.base_use_case.UseCase` — not just style.
    A subclass that multiply-inherits from this *and* a module's own
    ABC+Generic repository interface (e.g.
    `DjangoEmployeeRepository(DjangoBaseRepository[...], EmployeeRepository)`)
    needs both hierarchies to agree on the relative order of ABC and
    Generic, or Python's C3 linearization has no consistent MRO to
    produce — it doesn't matter which order is chosen, only that every
    ABC+Generic base in the project picks the same one.
    """

    model: type[ModelT]

    @abstractmethod
    def _to_entity(self, record: ModelT) -> EntityT:
        raise NotImplementedError

    @abstractmethod
    def _to_record_kwargs(self, entity: EntityT) -> dict[str, object]:
        """Field values for `Model(**kwargs)` / `update_or_create(defaults=kwargs)`.
        Excludes `id` — callers set that explicitly, see `create`/`update`."""
        raise NotImplementedError

    def _base_queryset(self) -> models.QuerySet:
        """Hook for subclasses that need `select_related`/`prefetch_related`
        on every read — override rather than repeating it in every method."""
        return self.model.objects.all()

    def get_by_id(self, entity_id: uuid.UUID) -> EntityT | None:
        record = self._base_queryset().filter(id=entity_id).first()
        return self._to_entity(record) if record is not None else None

    def exists(self, entity_id: uuid.UUID) -> bool:
        return self.model.objects.filter(id=entity_id).exists()

    def list(self, query: QueryParams) -> PageResult[EntityT]:
        queryset = self._base_queryset()

        if query.filters:
            queryset = queryset.filter(**query.filters)

        if query.search and query.search_fields:
            search_condition = Q()
            for field_name in query.search_fields:
                search_condition |= Q(**{f"{field_name}__icontains": query.search})
            queryset = queryset.filter(search_condition)

        total_count = queryset.count()

        if query.ordering:
            queryset = queryset.order_by(*query.ordering)

        start = (query.page - 1) * query.page_size
        end = start + query.page_size
        items = [self._to_entity(record) for record in queryset[start:end]]

        return PageResult(items=items, total_count=total_count, page=query.page, page_size=query.page_size)

    def create(self, entity: EntityT) -> EntityT:
        record = self.model(id=entity.id, **self._to_record_kwargs(entity))  # type: ignore[attr-defined]
        record.save()
        return self._to_entity(self._base_queryset().get(id=record.pk))

    def update(self, entity: EntityT) -> EntityT:
        self.model.objects.filter(id=entity.id).update(**self._to_record_kwargs(entity))  # type: ignore[attr-defined]
        return self._to_entity(self._base_queryset().get(id=entity.id))  # type: ignore[attr-defined]

    def delete(self, entity_id: uuid.UUID) -> None:
        record = self.model.objects.filter(id=entity_id).first()
        if record is not None:
            record.delete()  # honors SoftDeleteModel's override when the model uses it
