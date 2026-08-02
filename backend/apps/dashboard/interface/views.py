"""Dashboard HTTP endpoints.

Four granular `APIView`s rather than one "get everything" endpoint —
deliberately, matching the Phase 14 requirement that new widgets/cards must
be addable without structural changes: each endpoint backs one family of
widgets, is independently permission-gated by the same permission code that
already governs that data through its owning module, and can be polled by
the frontend at its own interval. Every method does exactly three things —
call the service, serialize, return — no business logic (CODING_STANDARD.md),
matching every other view in this codebase.
"""
from __future__ import annotations

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.dashboard.interface import dependencies
from apps.dashboard.interface.permissions import (
    HasPermission,
    VIEW_ATTENDANCE,
    VIEW_EMPLOYEES,
    VIEW_LEAVE,
)
from apps.dashboard.interface.serializers import (
    EmployeeStatisticsResponseSerializer,
    LeaveStatisticsResponseSerializer,
    RecentActivityItemSerializer,
    UpcomingHolidaySerializer,
)
from shared_kernel.api.response import success_response

_DEFAULT_RECENT_ACTIVITY_LIMIT = 10
_MAX_RECENT_ACTIVITY_LIMIT = 50
_DEFAULT_UPCOMING_HOLIDAYS_LIMIT = 5
_MAX_UPCOMING_HOLIDAYS_LIMIT = 20


def _parse_limit(request: Request, *, default: int, maximum: int) -> int:
    raw = request.query_params.get("limit")
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(1, min(value, maximum))


class EmployeeStatisticsView(APIView):
    """GET /api/v1/dashboard/employee-statistics/ — headcount, status, and
    department breakdowns. Requires employees.view_employees (the same
    permission that already gates reading Employee data everywhere else)."""

    permission_classes = [HasPermission(VIEW_EMPLOYEES)]

    @extend_schema(
        summary="Employee statistics for the Dashboard",
        description="Requires employees.view_employees.",
        responses={200: EmployeeStatisticsResponseSerializer},
    )
    def get(self, request: Request, *args, **kwargs) -> Response:
        result = dependencies.build_dashboard_service().get_employee_statistics()
        return success_response(EmployeeStatisticsResponseSerializer(result).data)


class LeaveStatisticsView(APIView):
    """GET /api/v1/dashboard/leave-statistics/ — status/type breakdowns,
    monthly trend, and today's on-leave count. Requires leave.view_leave."""

    permission_classes = [HasPermission(VIEW_LEAVE)]

    @extend_schema(
        summary="Leave statistics for the Dashboard",
        description="Requires leave.view_leave.",
        responses={200: LeaveStatisticsResponseSerializer},
    )
    def get(self, request: Request, *args, **kwargs) -> Response:
        result = dependencies.build_dashboard_service().get_leave_statistics()
        return success_response(LeaveStatisticsResponseSerializer(result).data)


class RecentActivityView(APIView):
    """GET /api/v1/dashboard/recent-activity/?limit=10 — the most recently
    changed leave requests across every employee. Requires leave.view_leave
    (same permission that gates Leave's own HR-wide processing queue,
    `ManageLeaveRequestsView`, since this reuses that exact read)."""

    permission_classes = [HasPermission(VIEW_LEAVE)]

    @extend_schema(
        summary="Recent leave activity for the Dashboard",
        description="Requires leave.view_leave.",
        parameters=[
            OpenApiParameter(
                name="limit",
                type=int,
                required=False,
                description=f"Max rows to return (default {_DEFAULT_RECENT_ACTIVITY_LIMIT}, "
                f"capped at {_MAX_RECENT_ACTIVITY_LIMIT}).",
            )
        ],
        responses={200: RecentActivityItemSerializer(many=True)},
    )
    def get(self, request: Request, *args, **kwargs) -> Response:
        limit = _parse_limit(
            request, default=_DEFAULT_RECENT_ACTIVITY_LIMIT, maximum=_MAX_RECENT_ACTIVITY_LIMIT
        )
        results = dependencies.build_dashboard_service().get_recent_activity(limit=limit)
        return success_response(RecentActivityItemSerializer(results, many=True).data)


class UpcomingHolidaysView(APIView):
    """GET /api/v1/dashboard/upcoming-holidays/?limit=5 — the next active
    holidays on or after today. Requires attendance.view_attendance."""

    permission_classes = [HasPermission(VIEW_ATTENDANCE)]

    @extend_schema(
        summary="Upcoming holidays for the Dashboard",
        description="Requires attendance.view_attendance.",
        parameters=[
            OpenApiParameter(
                name="limit",
                type=int,
                required=False,
                description=f"Max rows to return (default {_DEFAULT_UPCOMING_HOLIDAYS_LIMIT}, "
                f"capped at {_MAX_UPCOMING_HOLIDAYS_LIMIT}).",
            )
        ],
        responses={200: UpcomingHolidaySerializer(many=True)},
    )
    def get(self, request: Request, *args, **kwargs) -> Response:
        limit = _parse_limit(
            request, default=_DEFAULT_UPCOMING_HOLIDAYS_LIMIT, maximum=_MAX_UPCOMING_HOLIDAYS_LIMIT
        )
        results = dependencies.build_dashboard_service().get_upcoming_holidays(limit=limit)
        return success_response(UpcomingHolidaySerializer(results, many=True).data)
