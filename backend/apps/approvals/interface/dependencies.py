"""Composition root for the Approval Engine module's services.

Matches `apps/leave/interface/dependencies.py`'s pattern exactly: views
never construct infrastructure classes directly, they call one of these
factory functions — the one file in this module allowed to import
application-layer services and infrastructure-layer implementations
together.
"""
from __future__ import annotations

from apps.approvals.application.registry import chain_resolver_registry
from apps.approvals.application.services.approval_service import ApprovalService
from apps.approvals.infrastructure.authorization_adapter import IdentityAuthorizationAdapter
from apps.approvals.infrastructure.employee_lookup_adapter import EmployeeServiceLookupAdapter
from apps.approvals.infrastructure.repositories import (
    DjangoApprovalRequestRepository,
    DjangoApprovalStepRepository,
)
from apps.approvals.infrastructure.telegram_notification_adapter import CeleryTelegramNotificationAdapter
from shared_kernel.infrastructure.django_unit_of_work import DjangoUnitOfWork
from shared_kernel.infrastructure.event_bus_impl import event_bus


def build_approval_service() -> ApprovalService:
    employee_lookup = EmployeeServiceLookupAdapter()
    return ApprovalService(
        approval_request_repository=DjangoApprovalRequestRepository(),
        approval_step_repository=DjangoApprovalStepRepository(),
        chain_resolvers=chain_resolver_registry,
        notifications=CeleryTelegramNotificationAdapter(employee_lookup=employee_lookup),
        authorization=IdentityAuthorizationAdapter(),
        employee_lookup=employee_lookup,
        unit_of_work=DjangoUnitOfWork(),
        event_bus=event_bus,
    )


def build_employee_lookup() -> EmployeeServiceLookupAdapter:
    """Exposed separately (not just used internally by
    `build_approval_service`) because `interface/views.py` also needs it
    directly, to resolve a caller's `user_id`/`telegram_user_id` down to an
    employee id before calling `ApprovalService` — the same "resolve who's
    calling, then call the service" shape
    `apps.leave.interface.views.py` already uses via
    `LeaveService.resolve_employee_id_for_user`/`_telegram_user`."""
    return EmployeeServiceLookupAdapter()
