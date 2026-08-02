"""Adapter implementing `UserLookupPort` against `apps.identity`'s
already-composed public use case, matching
`apps.leave.infrastructure.employee_lookup_adapter`'s precedent exactly —
this is the one file in this module allowed to import `apps.identity`,
and even here only its public composition root
(`apps.identity.interface.dependencies.build_get_user_by_id_use_case`) and
public domain exceptions, never its infrastructure repositories or ORM
models directly.
"""
from __future__ import annotations

import uuid

from apps.employees.application.ports import UserLookupPort
from apps.identity.domain.exceptions import UserNotFoundError
from apps.identity.interface import dependencies as identity_dependencies


class UserServiceLookupAdapter(UserLookupPort):
    def user_exists(self, user_id: uuid.UUID) -> bool:
        try:
            identity_dependencies.build_get_user_by_id_use_case().execute(user_id)
        except UserNotFoundError:
            return False
        return True

    def get_user_email(self, user_id: uuid.UUID) -> str | None:
        try:
            result = identity_dependencies.build_get_user_by_id_use_case().execute(user_id)
        except UserNotFoundError:
            return None
        return result.email
