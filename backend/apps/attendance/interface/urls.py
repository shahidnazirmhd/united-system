"""Explicit path() routing, matching every other module's convention."""
from __future__ import annotations

from django.urls import path

from apps.attendance.interface.viewsets import HolidayViewSet

urlpatterns = [
    path(
        "holidays/",
        HolidayViewSet.as_view({"get": "list", "post": "create"}),
        name="holiday-list-create",
    ),
    path(
        "holidays/<uuid:pk>/",
        HolidayViewSet.as_view({"get": "retrieve", "patch": "update"}),
        name="holiday-detail",
    ),
]
