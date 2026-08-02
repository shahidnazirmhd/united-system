"""Adapter implementing `LeaveStatisticsPort` against `apps.leave`'s
already-composed public `LeaveService` — the one file in this module
allowed to import `apps.leave`, and even then only its public composition
root (`build_leave_service`), never that module's infrastructure/ORM layer
directly.

`get_recent_activity` reuses `LeaveService.list_all_requests_admin` (the
same read that backs Leave's own HR-wide processing queue,
`ManageLeaveRequestsView`) with no filters and `ordering=("-updated_at",)`
— see `LeaveRequestResponse.updated_at`'s docstring in `apps.leave` for why
that single column, already present on every lifecycle transition, is
sufficient to build a correct "recently changed" feed with zero new query
logic on Leave's side.
"""
from __future__ import annotations

from apps.dashboard.application.dtos import (
    LeaveMonthlyStat,
    LeaveStatisticsResponse,
    LeaveTypeStat,
    RecentActivityItem,
)
from apps.dashboard.application.ports import LeaveStatisticsPort
from apps.leave.interface import dependencies as leave_dependencies
from shared_kernel.domain.repository import QueryParams


class LeaveServiceStatisticsAdapter(LeaveStatisticsPort):
    def get_statistics(self) -> LeaveStatisticsResponse:
        source = leave_dependencies.build_leave_service().get_statistics()
        return LeaveStatisticsResponse(
            status_breakdown=dict(source.status_breakdown),
            leave_type_breakdown=[
                LeaveTypeStat(
                    leave_type_id=stat.leave_type_id,
                    leave_type_name=stat.leave_type_name,
                    count=stat.count,
                )
                for stat in source.leave_type_breakdown
            ],
            monthly_trend=[
                LeaveMonthlyStat(month=stat.month, count=stat.count) for stat in source.monthly_trend
            ],
            on_leave_today_count=source.on_leave_today_count,
        )

    def get_recent_activity(self, *, limit: int) -> list[RecentActivityItem]:
        page_result = leave_dependencies.build_leave_service().list_all_requests_admin(
            query=QueryParams(filters={}, ordering=("-updated_at",), page=1, page_size=limit)
        )
        return [
            RecentActivityItem(
                leave_request_id=request.id,
                employee_id=request.employee_id,
                employee_name=request.employee_name,
                employee_code=request.employee_code,
                leave_type_name=request.leave_type_name,
                status=request.status,
                start_date=request.start_date,
                end_date=request.end_date,
                updated_at=request.updated_at,
            )
            for request in page_result.items
        ]
