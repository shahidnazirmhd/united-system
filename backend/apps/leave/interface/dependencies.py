"""Composition root for the Leave module's services.

Matches apps/employees/interface/dependencies.py's pattern exactly: views
never construct infrastructure classes directly, they call one of these
factory functions — the one file in this module allowed to import
application-layer services and infrastructure-layer implementations (of
this module, and of the `EmployeeLookupPort` adapter into Employees)
together.
"""
from __future__ import annotations

from django.conf import settings

from apps.leave.application.services.leave_balance_service import LeaveBalanceService
from apps.leave.application.services.leave_request_service import LeaveRequestService
from apps.leave.application.services.leave_service import LeaveService
from apps.leave.application.services.leave_validation_service import LeaveValidationService
from apps.leave.infrastructure.employee_lookup_adapter import EmployeeServiceLookupAdapter
from apps.leave.infrastructure.repositories import (
    DjangoLeaveBalanceRepository,
    DjangoLeaveRequestRepository,
    DjangoLeaveTypeRepository,
)
from shared_kernel.infrastructure.django_unit_of_work import DjangoUnitOfWork
from shared_kernel.infrastructure.event_bus_impl import event_bus


def build_leave_balance_service() -> LeaveBalanceService:
    return LeaveBalanceService(
        leave_balance_repository=DjangoLeaveBalanceRepository(),
        leave_type_repository=DjangoLeaveTypeRepository(),
        leave_request_repository=DjangoLeaveRequestRepository(),
        unit_of_work=DjangoUnitOfWork(),
    )


def build_leave_validation_service() -> LeaveValidationService:
    return LeaveValidationService(
        leave_type_repository=DjangoLeaveTypeRepository(),
        leave_balance_repository=DjangoLeaveBalanceRepository(),
        leave_request_repository=DjangoLeaveRequestRepository(),
        employee_lookup=EmployeeServiceLookupAdapter(),
        allow_past_start_date=settings.LEAVE_ALLOW_PAST_START_DATE,
    )


def build_leave_request_service() -> LeaveRequestService:
    return LeaveRequestService(
        leave_request_repository=DjangoLeaveRequestRepository(),
        leave_type_repository=DjangoLeaveTypeRepository(),
        validation_service=build_leave_validation_service(),
        balance_service=build_leave_balance_service(),
        unit_of_work=DjangoUnitOfWork(),
        event_bus=event_bus,
    )


def build_leave_service() -> LeaveService:
    return LeaveService(
        leave_type_repository=DjangoLeaveTypeRepository(),
        balance_service=build_leave_balance_service(),
        request_service=build_leave_request_service(),
        employee_lookup=EmployeeServiceLookupAdapter(),
    )
