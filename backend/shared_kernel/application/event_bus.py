"""Abstract publish/subscribe contract for domain events.

The concrete implementation lives in
shared_kernel/infrastructure/event_bus_impl.py. Application-layer code only
ever depends on this interface — Dependency Inversion applied to the
messaging concern, matching the pattern used for the Unit of Work.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable

from shared_kernel.domain.domain_event import DomainEvent

EventHandler = Callable[[DomainEvent], None]


class EventBus(ABC):
    @abstractmethod
    def publish(self, event: DomainEvent) -> None:
        raise NotImplementedError

    @abstractmethod
    def subscribe(self, event_type: type[DomainEvent], handler: EventHandler) -> None:
        raise NotImplementedError
