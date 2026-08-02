"""In-process, synchronous event bus.

Deliberately the simplest implementation that satisfies the EventBus
interface: today, zero modules exist to subscribe to anything, so a
distributed/Redis-backed pub-sub implementation would be complexity with no
current payoff (PROJECT_SPEC.md: "avoid unnecessary complexity"). Because
every caller depends only on the EventBus interface (Dependency Inversion),
swapping this for a Redis-pub-sub or Celery-task-based implementation later
— needed once Approvals/Notifications subscribe to events raised by other
modules — is a change to this one file only, not to any module that
publishes or subscribes.
"""
from __future__ import annotations

import logging
from collections import defaultdict

from shared_kernel.application.event_bus import EventBus, EventHandler
from shared_kernel.domain.domain_event import DomainEvent

logger = logging.getLogger(__name__)


class InProcessEventBus(EventBus):
    def __init__(self) -> None:
        self._handlers: dict[type[DomainEvent], list[EventHandler]] = defaultdict(list)

    def publish(self, event: DomainEvent) -> None:
        handlers = self._handlers.get(type(event), [])
        logger.debug("Publishing %s to %d handler(s)", type(event).__name__, len(handlers))
        for handler in handlers:
            try:
                handler(event)
            except Exception:
                # Fault isolation between publisher and subscriber: a
                # subscriber's own business-rule failure (e.g. Leave's
                # handle_approval_decided raising leave_request_not_found
                # for a subject_id it doesn't recognize) must never surface
                # as a failure of whatever call published the event — the
                # publishing module (e.g. apps.approvals, which has no idea
                # Leave or any other subscriber even exists) already
                # committed its own write and returned its own response by
                # this point. This is also the behavior any real
                # asynchronous replacement (Celery-task-per-handler, this
                # class's own docstring anticipates one) would have for
                # free, since a failed task there doesn't fail the
                # publisher's request either — logging here keeps this
                # synchronous implementation's failure mode consistent with
                # that eventual one, rather than a synchronous-only quirk.
                logger.exception(
                    "Event handler %r raised while handling %s — isolated, event not redelivered.",
                    handler,
                    type(event).__name__,
                )

    def subscribe(self, event_type: type[DomainEvent], handler: EventHandler) -> None:
        self._handlers[event_type].append(handler)


event_bus = InProcessEventBus()
