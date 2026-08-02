"""In-process registry mapping a `subject_type` string to the
`ApprovalChainResolverPort` implementation that knows how to resolve
approvers for that subject.

Deliberately the simplest possible implementation — a plain dict wrapped in
a small class — matching
`shared_kernel/infrastructure/event_bus_impl.py`'s "simplest thing that
satisfies the interface" discipline for the identical reason: exactly one
process-wide registry is ever needed (no distributed/shared state across
workers is required — each Django worker process registers the same
resolvers at startup via every subject module's own `AppConfig.ready()`,
mirroring `EventBus.subscribe()`'s registration pattern exactly).

Registration happens at Django app-startup time (`apps/leave/apps.py`'s
`ready()`), never at request time — by the time any HTTP request reaches
`ApprovalService`, every subject module's resolver is already registered
for the lifetime of the process, exactly like `event_bus.subscribe()`
calls are all made once at startup, not per-request.
"""
from __future__ import annotations

from apps.approvals.application.ports import ApprovalChainResolverPort


class ApprovalChainResolverRegistry:
    def __init__(self) -> None:
        self._resolvers: dict[str, ApprovalChainResolverPort] = {}

    def register(self, subject_type: str, resolver: ApprovalChainResolverPort) -> None:
        self._resolvers[subject_type] = resolver

    def get(self, subject_type: str) -> ApprovalChainResolverPort | None:
        return self._resolvers.get(subject_type)


#: Process-wide singleton, exactly like
#: `shared_kernel.infrastructure.event_bus_impl.event_bus` — imported both
#: by subject modules (to register into, e.g.
#: `apps/leave/apps.py`) and by this module's own composition root
#: (`interface/dependencies.py`, to hand to `ApprovalService`).
chain_resolver_registry = ApprovalChainResolverRegistry()
