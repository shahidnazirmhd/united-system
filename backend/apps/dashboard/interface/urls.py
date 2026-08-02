"""Explicit path() routing, matching every other module's convention."""
from __future__ import annotations

from django.urls import path

from apps.dashboard.interface.views import (
    EmployeeStatisticsView,
    LeaveStatisticsView,
    RecentActivityView,
    UpcomingHolidaysView,
)

urlpatterns = [
    path("employee-statistics/", EmployeeStatisticsView.as_view(), name="dashboard-employee-statistics"),
    path("leave-statistics/", LeaveStatisticsView.as_view(), name="dashboard-leave-statistics"),
    path("recent-activity/", RecentActivityView.as_view(), name="dashboard-recent-activity"),
    path("upcoming-holidays/", UpcomingHolidaysView.as_view(), name="dashboard-upcoming-holidays"),
]
