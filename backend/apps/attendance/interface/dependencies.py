"""Composition root for the Attendance module's services — matching every
other module's interface/dependencies.py pattern exactly."""
from __future__ import annotations

from apps.attendance.application.services.holiday_command_service import HolidayCommandService
from apps.attendance.application.services.holiday_query_service import HolidayQueryService
from apps.attendance.application.services.holiday_service import HolidayService
from apps.attendance.infrastructure.leave_reference_check_adapter import LeaveServiceReferenceCheckAdapter
from apps.attendance.infrastructure.repositories import DjangoHolidayRepository
from shared_kernel.infrastructure.django_unit_of_work import DjangoUnitOfWork


def build_holiday_command_service() -> HolidayCommandService:
    return HolidayCommandService(
        holiday_repository=DjangoHolidayRepository(),
        unit_of_work=DjangoUnitOfWork(),
        # Round 15 item 3 — see apps.attendance.application.ports
        # .LeaveReferenceCheckPort's docstring.
        leave_reference_check=LeaveServiceReferenceCheckAdapter(),
    )


def build_holiday_query_service() -> HolidayQueryService:
    return HolidayQueryService(holiday_repository=DjangoHolidayRepository())


def build_holiday_service() -> HolidayService:
    return HolidayService(
        command_service=build_holiday_command_service(),
        query_service=build_holiday_query_service(),
        holiday_repository=DjangoHolidayRepository(),
    )
