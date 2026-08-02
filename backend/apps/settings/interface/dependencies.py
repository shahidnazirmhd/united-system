"""Composition root for the Settings module's service — matching every
other module's interface/dependencies.py pattern exactly."""
from __future__ import annotations

from apps.settings.application.services.settings_service import SettingsService
from apps.settings.infrastructure.leave_reference_check_adapter import LeaveServiceReferenceCheckAdapter
from apps.settings.infrastructure.repositories import DjangoSettingRepository


def build_settings_service() -> SettingsService:
    return SettingsService(
        repository=DjangoSettingRepository(),
        # Round 15 item 4 — see apps.settings.application.ports
        # .LeaveReferenceCheckPort's docstring.
        leave_reference_check=LeaveServiceReferenceCheckAdapter(),
    )
