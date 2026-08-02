"""Composition root for the Dashboard module's service — matching every
other module's `interface/dependencies.py` pattern exactly."""
from __future__ import annotations

from apps.dashboard.application.services.dashboard_service import DashboardService
from apps.dashboard.infrastructure.employee_statistics_adapter import (
    EmployeeServiceStatisticsAdapter,
)
from apps.dashboard.infrastructure.holiday_lookup_adapter import HolidayServiceLookupAdapter
from apps.dashboard.infrastructure.leave_statistics_adapter import LeaveServiceStatisticsAdapter


def build_dashboard_service() -> DashboardService:
    return DashboardService(
        employee_statistics=EmployeeServiceStatisticsAdapter(),
        leave_statistics=LeaveServiceStatisticsAdapter(),
        holiday_lookup=HolidayServiceLookupAdapter(),
    )
