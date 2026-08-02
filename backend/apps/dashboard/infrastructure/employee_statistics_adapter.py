"""Adapter implementing `EmployeeStatisticsPort` against `apps.employees`'s
already-composed public `EmployeeQueryService` — the one file in this
module allowed to import `apps.employees`, and even then only its public
composition root (`build_employee_query_service`), never that module's
infrastructure/ORM layer directly.
"""
from __future__ import annotations

from apps.dashboard.application.dtos import (
    EmployeeDepartmentStat,
    EmployeeStatisticsResponse,
)
from apps.dashboard.application.ports import EmployeeStatisticsPort
from apps.employees.interface import dependencies as employees_dependencies


class EmployeeServiceStatisticsAdapter(EmployeeStatisticsPort):
    def get_statistics(self) -> EmployeeStatisticsResponse:
        source = employees_dependencies.build_employee_query_service().get_statistics()
        return EmployeeStatisticsResponse(
            total_employees=source.total_employees,
            active_count=source.active_count,
            inactive_count=source.inactive_count,
            terminated_count=source.terminated_count,
            status_breakdown=dict(source.status_breakdown),
            current_status_breakdown=dict(source.current_status_breakdown),
            employment_type_breakdown=dict(source.employment_type_breakdown),
            department_breakdown=[
                EmployeeDepartmentStat(
                    department_id=stat.department_id,
                    department_name=stat.department_name,
                    count=stat.count,
                )
                for stat in source.department_breakdown
            ],
            new_hires_this_month=source.new_hires_this_month,
        )
