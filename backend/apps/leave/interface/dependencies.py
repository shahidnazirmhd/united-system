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
from apps.leave.application.services.leave_type_service import LeaveTypeService
from apps.leave.application.services.leave_validation_service import LeaveValidationService
from apps.leave.infrastructure.approval_request_adapter import ApprovalServiceRequestAdapter
from apps.leave.infrastructure.employee_lookup_adapter import (
    EmployeeServiceLookupAdapter,
    EmployeeStatusServiceAdapter,
)
from apps.leave.infrastructure.holiday_lookup_adapter import HolidayServiceLookupAdapter
from apps.leave.infrastructure.leave_notification_adapter import CeleryLeaveNotificationAdapter
from apps.leave.infrastructure.repositories import (
    DjangoLeaveBalanceAdjustmentRepository,
    DjangoLeaveBalanceRepository,
    DjangoLeaveRequestRepository,
    DjangoLeaveTypeRepository,
)
from apps.leave.infrastructure.settings_lookup_adapter import SettingsServiceLookupAdapter
from shared_kernel.infrastructure.django_unit_of_work import DjangoUnitOfWork
from shared_kernel.infrastructure.event_bus_impl import event_bus


def build_leave_balance_service() -> LeaveBalanceService:
    return LeaveBalanceService(
        leave_balance_repository=DjangoLeaveBalanceRepository(),
        leave_type_repository=DjangoLeaveTypeRepository(),
        leave_request_repository=DjangoLeaveRequestRepository(),
        unit_of_work=DjangoUnitOfWork(),
        # Both only used by adjust_balance (Phase 13) — see that method's
        # docstring; every pre-existing caller of this factory is
        # unaffected.
        employee_lookup=EmployeeServiceLookupAdapter(),
        balance_adjustment_repository=DjangoLeaveBalanceAdjustmentRepository(),
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
        approval_requests=ApprovalServiceRequestAdapter(),
        settings_lookup=SettingsServiceLookupAdapter(),
        holiday_lookup=HolidayServiceLookupAdapter(),
        employee_status=EmployeeStatusServiceAdapter(),
        # Round 15 item 6 — see LeaveNotificationPort's docstring.
        notifications=CeleryLeaveNotificationAdapter(employee_lookup=EmployeeServiceLookupAdapter()),
    )


def build_employee_status_adapter() -> EmployeeStatusServiceAdapter:
    """Round 14 items 6/8 — the write-side port into Employees' Current
    Status, used by the leave-status daily reconciliation Celery task
    (tasks.py) and by LeaveRequestService's immediate-transition calls at
    approve/cancel time. A thin factory of its own (not folded into
    build_leave_request_service) since the Celery task needs it standalone,
    without constructing a whole LeaveRequestService."""
    return EmployeeStatusServiceAdapter()


def build_leave_type_service() -> LeaveTypeService:
    return LeaveTypeService(
        leave_type_repository=DjangoLeaveTypeRepository(),
        unit_of_work=DjangoUnitOfWork(),
        # Round 15 item 5 — see LeaveTypeService.__init__'s docstring.
        leave_request_repository=DjangoLeaveRequestRepository(),
    )


def build_leave_service() -> LeaveService:
    return LeaveService(
        leave_type_repository=DjangoLeaveTypeRepository(),
        balance_service=build_leave_balance_service(),
        request_service=build_leave_request_service(),
        employee_lookup=EmployeeServiceLookupAdapter(),
        leave_type_service=build_leave_type_service(),
    )
