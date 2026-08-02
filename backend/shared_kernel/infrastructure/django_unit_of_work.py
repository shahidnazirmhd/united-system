"""Django ORM-backed implementation of the abstract UnitOfWork."""
from __future__ import annotations

from types import TracebackType
from typing import Callable

from django.db import transaction

from shared_kernel.application.unit_of_work import UnitOfWork


class DjangoUnitOfWork(UnitOfWork):
    def __init__(self) -> None:
        self._atomic = transaction.atomic()

    def __enter__(self) -> "DjangoUnitOfWork":
        self._atomic.__enter__()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self._atomic.__exit__(exc_type, exc_val, exc_tb)

    def commit(self) -> None:
        # Commit happens implicitly when the atomic block exits cleanly;
        # this method exists to satisfy the abstract interface and to give
        # a use case an explicit statement of intent at the end of a flow.
        pass

    def rollback(self) -> None:
        transaction.set_rollback(True)

    def on_commit(self, callback: Callable[[], None]) -> None:
        # The one place `django.db.transaction` is allowed to leak in for
        # this concern — application-layer callers (e.g. ApprovalService)
        # only ever see UnitOfWork.on_commit's abstract signature, never
        # this import, keeping Clean Architecture's dependency rule intact.
        # Deferring to Django's own mechanism is correct even outside an
        # atomic block: Django runs the callback immediately in that case,
        # which is exactly what "nothing to wait for" should mean here too.
        transaction.on_commit(callback)
