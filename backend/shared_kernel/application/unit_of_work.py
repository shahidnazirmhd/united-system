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
