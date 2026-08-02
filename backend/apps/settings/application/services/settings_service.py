"""Settings' one application service.

Not built on `BaseService` (that base is keyed by UUID `id` — see
`domain/repositories.py`'s docstring for why this module's repository
contract is deliberately different). This is a small, hand-written
service, matching the shape Identity used before `BaseService` existed.

`_KNOWN_SETTINGS` is this module's only concession to knowing anything
about specific settings' shape — a minimal, opt-in validation registry so
`update_setting` can reject an obviously wrong value (e.g. a string where
`default_week_off` needs 0-6) without requiring every future setting to
register a validator (an unregistered key is only checked for existing,
which is registered by the seed migration that creates it).
"""
from __future__ import annotations

from typing import Any, Callable

from apps.settings.application.dtos import SettingResponse, UpdateSettingRequest
from apps.settings.application.ports import LeaveReferenceCheckPort
from apps.settings.domain.exceptions import (
    InvalidSettingValueError,
    SettingNotFoundError,
    SettingReferencedByLeaveRequestError,
)
from apps.settings.domain.repositories import SettingRepository


def _validate_week_off(value: Any) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or not (0 <= value <= 6):
        raise InvalidSettingValueError(
            "default_week_off must be an integer 0-6 (0=Monday ... 6=Sunday)."
        )


# Keyed by setting `key` — see this class's docstring.
_KNOWN_SETTINGS: dict[str, Callable[[Any], None]] = {
    "default_week_off": _validate_week_off,
}

# Round 15 item 4 — settings whose value a real leave request's frozen
# `working_days` depends on. Only `default_week_off` today; a future
# referentially-sensitive setting registers itself here the same way, not
# by editing `update_setting` itself (Open/Closed, matching
# `_KNOWN_SETTINGS`'s own registry shape above).
_REFERENTIALLY_GUARDED_SETTINGS = frozenset({"default_week_off"})


def _to_response(setting) -> SettingResponse:
    return SettingResponse(key=setting.key, value=setting.value, description=setting.description)


class SettingsService:
    def __init__(
        self,
        repository: SettingRepository,
        leave_reference_check: LeaveReferenceCheckPort | None = None,
    ) -> None:
        self._repository = repository
        # Round 15 item 4 — see apps.settings.application.ports
        # .LeaveReferenceCheckPort's docstring. Optional (default None) so
        # any existing test construction of this service keeps working
        # unchanged; only `default_week_off` (the one key with a
        # referential-integrity rule) requires it — see
        # `_REFERENTIALLY_GUARDED_SETTINGS` below.
        self._leave_reference_check = leave_reference_check

    def list_settings(self) -> list[SettingResponse]:
        return [_to_response(s) for s in self._repository.list_all()]

    def get_by_key(self, key: str) -> SettingResponse:
        setting = self._repository.get_by_key(key)
        if setting is None:
            raise SettingNotFoundError()
        return _to_response(setting)

    def get_value(self, key: str, *, default: Any = None) -> Any:
        """Read path for other modules' port adapters (e.g. Leave's
        SettingsLookupPort) — returns `default` rather than raising when a
        settings row is somehow missing (a nightly working-day calculation
        should degrade gracefully, not hard-fail, if a setting was deleted
        directly in the database outside the normal update path)."""
        setting = self._repository.get_by_key(key)
        return setting.value if setting is not None else default

    def update_setting(self, request: UpdateSettingRequest) -> SettingResponse:
        validator = _KNOWN_SETTINGS.get(request.key)
        if validator is not None:
            validator(request.value)
        if request.key in _REFERENTIALLY_GUARDED_SETTINGS and self._leave_reference_check is not None:
            if self._leave_reference_check.has_any_active_leave_request():
                raise SettingReferencedByLeaveRequestError()
        updated = self._repository.update_value(
            key=request.key, value=request.value, updated_by=request.updated_by
        )
        return _to_response(updated)
