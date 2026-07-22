"""Explicit path() routing, matching Identity's/Employees' convention (no
DRF router "magic" — every endpoint's exact path is visible here)."""
from __future__ import annotations

from django.urls import path

from apps.leave.interface.views import (
    ApplyLeaveTelegramView,
    CancelLeaveRequestView,
    CancelLeaveTelegramView,
    EmployeeLeaveBalanceView,
    EmployeeLeaveHistoryView,
    LeaveBalanceTelegramView,
    LeaveHistoryTelegramView,
    LeaveRequestDetailTelegramView,
    LeaveRequestDetailView,
    LeaveRequestListCreateView,
    LeaveTypeListView,
    LeaveTypesTelegramView,
    MyLeaveBalanceView,
)

urlpatterns = [
    # --- Self-service / HR (JWT) -----------------------------------
    path("types/", LeaveTypeListView.as_view(), name="leave-type-list"),
    path("balance/me/", MyLeaveBalanceView.as_view(), name="leave-balance-me"),
    path("balance/<uuid:employee_id>/", EmployeeLeaveBalanceView.as_view(), name="leave-balance-employee"),
    path("requests/", LeaveRequestListCreateView.as_view(), name="leave-request-list-create"),
    path(
        "requests/employee/<uuid:employee_id>/",
        EmployeeLeaveHistoryView.as_view(),
        name="leave-request-history-employee",
    ),
    path("requests/<uuid:pk>/", LeaveRequestDetailView.as_view(), name="leave-request-detail"),
    path("requests/<uuid:pk>/cancel/", CancelLeaveRequestView.as_view(), name="leave-request-cancel"),
    # --- Telegram Gateway-facing only (see interface/views.py) ----------
    path("telegram/types/", LeaveTypesTelegramView.as_view(), name="leave-telegram-type-list"),
    path("telegram/balance/", LeaveBalanceTelegramView.as_view(), name="leave-telegram-balance"),
    path("telegram/requests/", LeaveHistoryTelegramView.as_view(), name="leave-telegram-request-history"),
    path(
        "telegram/requests/apply/",
        ApplyLeaveTelegramView.as_view(),
        name="leave-telegram-request-apply",
    ),
    path(
        "telegram/requests/<uuid:pk>/",
        LeaveRequestDetailTelegramView.as_view(),
        name="leave-telegram-request-detail",
    ),
    path(
        "telegram/requests/<uuid:pk>/cancel/",
        CancelLeaveTelegramView.as_view(),
        name="leave-telegram-request-cancel",
    ),
]
