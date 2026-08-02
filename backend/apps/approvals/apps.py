from __future__ import annotations

from django.apps import AppConfig


class ApprovalsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.approvals"
    label = "approvals"

    def ready(self) -> None:
        """This module has nothing of its own to subscribe to at startup —
        unlike `apps.leave` (which both registers a chain resolver INTO
        this module and subscribes TO this module's `ApprovalDecided`
        event), `apps.approvals` itself never imports any subject module by
        name, in either direction. Its `AppConfig.ready()` is intentionally
        a no-op; this docstring exists so a future reader doesn't wonder
        whether an event-subscription/registration step was simply
        forgotten here — see `apps/leave/apps.py`'s `ready()` for where
        that wiring actually lives (on the *consuming* module's side, by
        design: a generic engine must never need to know its consumers
        exist)."""
