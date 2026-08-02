"""Abstract Unit of Work — the transaction boundary each use case controls
explicitly, rather than inheriting Django's default per-request transaction
(which is disabled globally — see ATOMIC_REQUESTS = False in
config/settings/base.py).

The application layer depends only on this interface, never on the concrete
Django implementation (shared_kernel/infrastructure/django_unit_of_work.py)
— Dependency Inversion applied to the transaction-management concern.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from types import TracebackType
from typing import Callable


class UnitOfWork(ABC):
    def __enter__(self) -> "UnitOfWork":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if exc_type is not None:
            self.rollback()
        else:
            self.commit()

    @abstractmethod
    def commit(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def rollback(self) -> None:
        raise NotImplementedError

    def on_commit(self, callback: Callable[[], None]) -> None:
        """Defer `callback` until this unit of work's transaction actually
        commits (e.g. `apps.approvals.application.services.approval_service`
        uses this so a Telegram notification is never dispatched for a
        database write that ends up rolling back).

        Deliberately NOT `@abstractmethod`: the correct default for anything
        that isn't a real, deferred-commit transaction (in particular every
        hand-rolled `FakeUnitOfWork` across the test suite, which has no
        Django connection to defer against at all) is to simply run the
        callback right away — exactly what "no transaction in progress"
        means in `DjangoUnitOfWork.on_commit`'s own real implementation too.
        Only a backend with an actual notion of "not yet committed" needs to
        override this — see `shared_kernel.infrastructure.django_unit_of_work.DjangoUnitOfWork`.
        """
        callback()
