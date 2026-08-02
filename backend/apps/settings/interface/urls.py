"""Explicit path() routing, matching every other module's convention."""
from __future__ import annotations

from django.urls import path

from apps.settings.interface.views import SettingDetailView, SettingListView

urlpatterns = [
    path("", SettingListView.as_view(), name="setting-list"),
    path("<str:key>/", SettingDetailView.as_view(), name="setting-detail"),
]
