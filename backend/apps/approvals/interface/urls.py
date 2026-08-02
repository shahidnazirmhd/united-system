"""Explicit path() routing, matching Identity's/Employees'/Leave's
convention (no DRF router "magic" — every endpoint's exact path is visible
here)."""
from __future__ import annotations

from django.urls import path

from apps.approvals.interface.views import (
    ApprovalHistoryBySubjectView,
    ApprovalRequestDetailView,
    DecideApprovalTelegramView,
    DecideApprovalView,
    MyPendingApprovalsView,
    PendingApprovalsTelegramView,
)

urlpatterns = [
    # --- Self-service / HR (JWT) -----------------------------------
    path("pending/me/", MyPendingApprovalsView.as_view(), name="approval-pending-me"),
    path(
        "subject/<str:subject_type>/<uuid:subject_id>/",
        ApprovalHistoryBySubjectView.as_view(),
        name="approval-history-by-subject",
    ),
    path("<uuid:pk>/", ApprovalRequestDetailView.as_view(), name="approval-detail"),
    path("<uuid:pk>/decide/", DecideApprovalView.as_view(), name="approval-decide"),
    # --- Telegram Gateway-facing only (see interface/views.py) ----------
    path("telegram/pending/", PendingApprovalsTelegramView.as_view(), name="approval-telegram-pending"),
    path("telegram/decide/", DecideApprovalTelegramView.as_view(), name="approval-telegram-decide"),
]
