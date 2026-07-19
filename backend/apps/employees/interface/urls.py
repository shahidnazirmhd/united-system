"""Explicit path() routing, matching Identity's convention (no DRF router
"magic" — every endpoint's exact path is visible here in one place)."""
from __future__ import annotations

from django.urls import path

from apps.employees.interface.telegram_views import (
    EmployeeTelegramLinkStatusView,
    EmployeeTelegramProfileView,
    EmployeeUnlinkTelegramView,
    RequestEmployeeTelegramLinkView,
    VerifyEmployeeTelegramLinkView,
)
from apps.employees.interface.viewsets import EmployeeViewSet

urlpatterns = [
    path(
        "",
        EmployeeViewSet.as_view({"get": "list", "post": "create"}),
        name="employee-list-create",
    ),
    path("search/", EmployeeViewSet.as_view({"get": "search"}), name="employee-search"),
    path("me/", EmployeeViewSet.as_view({"get": "me"}), name="employee-me"),
    # --- Telegram linking (Gateway-facing only — see telegram_views.py) --
    path(
        "telegram/link/request/",
        RequestEmployeeTelegramLinkView.as_view(),
        name="employee-telegram-link-request",
    ),
    path(
        "telegram/link/verify/",
        VerifyEmployeeTelegramLinkView.as_view(),
        name="employee-telegram-link-verify",
    ),
    path("telegram/unlink/", EmployeeUnlinkTelegramView.as_view(), name="employee-telegram-unlink"),
    path("telegram/status/", EmployeeTelegramLinkStatusView.as_view(), name="employee-telegram-status"),
    path("telegram/profile/", EmployeeTelegramProfileView.as_view(), name="employee-telegram-profile"),
    path(
        "<uuid:pk>/",
        EmployeeViewSet.as_view({"get": "retrieve", "patch": "update"}),
        name="employee-detail",
    ),
    path(
        "<uuid:pk>/activate/",
        EmployeeViewSet.as_view({"post": "activate"}),
        name="employee-activate",
    ),
    path(
        "<uuid:pk>/deactivate/",
        EmployeeViewSet.as_view({"post": "deactivate"}),
        name="employee-deactivate",
    ),
]
