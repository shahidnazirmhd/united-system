"""Explicit path() routing, matching Identity's/Employees' convention (no
DRF router "magic" — every endpoint's exact path is visible here)."""
from __future__ import annotations

from django.urls import path

from apps.leave.interface.views import (
    AdjustLeaveBalanceView,
    ApplyLeaveForEmployeeView,
    ApplyLeaveTelegramView,
    CancelLeaveForEmployeeView,
    CancelLeaveRequestView,
    CancelLeaveTelegramView,
    EmployeeLeaveBalanceView,
    EmployeeLeaveHistoryView,
    Level1ApprovalCheckView,
    LeaveBalanceTelegramView,
    LeaveHistoryTelegramView,
    LeaveRequestDetailTelegramView,
    LeaveRequestDetailView,
    LeaveRequestListCreateView,
    LeaveTypeListView,
    LeaveTypeManageDetailView,
    LeaveTypesTelegramView,
    ManageLeaveRequestsView,
    ManageLeaveTypesView,
    MyLeaveBalanceView,
)

urlpatterns = [
    # --- Self-service / HR (JWT) -----------------------------------
    path("types/", LeaveTypeListView.as_view(), name="leave-type-list"),
    path("types/manage/", ManageLeaveTypesView.as_view(), name="leave-type-manage-list-create"),
    path("types/manage/<uuid:pk>/", LeaveTypeManageDetailView.as_view(), name="leave-type-manage-detail"),
    path("balance/me/", MyLeaveBalanceView.as_view(), name="leave-balance-me"),
    path("balance/<uuid:employee_id>/", EmployeeLeaveBalanceView.as_view(), name="leave-balance-employee"),
    path("balances/adjust/", AdjustLeaveBalanceView.as_view(), name="leave-balance-adjust"),
    path("requests/", LeaveRequestListCreateView.as_view(), name="leave-request-list-create"),
    # NOTE: registered before "requests/employee/<uuid:employee_id>/" would
    # matter only if "manage" could itself parse as a UUID, which it can't —
    # order doesn't actually matter here, but kept adjacent to that view for
    # readability (both are HR-wide-vs-one-employee reads of the same data).
    path("requests/manage/", ManageLeaveRequestsView.as_view(), name="leave-request-manage-list"),
    path(
        "requests/employee/<uuid:employee_id>/",
        EmployeeLeaveHistoryView.as_view(),
        name="leave-request-history-employee",
    ),
    path(
        "requests/employee/<uuid:employee_id>/apply/",
        ApplyLeaveForEmployeeView.as_view(),
        name="leave-request-apply-for-employee",
    ),
    path(
        "requests/employee/<uuid:employee_id>/level1-approval-check/",
        Level1ApprovalCheckView.as_view(),
        name="leave-request-level1-approval-check",
    ),
    path("requests/<uuid:pk>/", LeaveRequestDetailView.as_view(), name="leave-request-detail"),
    path("requests/<uuid:pk>/cancel/", CancelLeaveRequestView.as_view(), name="leave-request-cancel"),
    path(
        "requests/<uuid:pk>/cancel-for-employee/",
        CancelLeaveForEmployeeView.as_view(),
        name="leave-request-cancel-for-employee",
    ),
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
