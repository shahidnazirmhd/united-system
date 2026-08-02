"""Domain/application exceptions for Settings.

All subclass shared_kernel's DomainError, matching every other module's
exceptions.py convention.
"""
from __future__ import annotations

from shared_kernel.api.exceptions import ConflictError, NotFoundError, ValidationError


class SettingNotFoundError(NotFoundError):
    """No setting was found with the given key.

    Settings are seed-only (see migrations/0003_seed_default_settings.py) —
    there is no "create a new setting" endpoint, so this also covers "you
    tried to update a key that doesn't exist yet."
    """

    code = "setting_not_found"


class InvalidSettingValueError(ValidationError):
    """The given value is not valid for this setting's key."""

    code = "invalid_setting_value"


class SettingReferencedByLeaveRequestError(ConflictError):
    """This setting cannot be changed because recorded or approved leave requests depend on it. Cancel the related leave request(s) first."""

    code = "setting_referenced_by_leave_request"
