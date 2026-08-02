"""Backs `apps.approvals`'s `ApprovalAuthorizationPort` — "what permission
codes does the user linked to this employee currently hold?" A thin
read, deliberately not a REST-facing use case (no view calls this
directly): the only caller is
`apps.approvals.infrastructure.authorization_adapter.IdentityAuthorizationAdapter`,
via this module's public composition root
(`interface/dependencies.py::build_get_permission_codes_for_employee_use_case`)
— the same "another module calls into our already-composed public
application layer, never our repositories directly" boundary every other
cross-module port in this codebase already follows.

Returns an empty `frozenset` rather than raising when the employee has no
linked user account (or none is found) — "no permissions" and "no user"
collapse to the same answer for this use case's one caller, which only ever
asks "can this employee decide a permission-gated approval step," never
"does this employee/user exist."
"""
from __future__ import annotations

import uuid

from apps.identity.domain.repositories import UserRepository
from shared_kernel.application.base_use_case import UseCase


class GetPermissionCodesForEmployeeUseCase(UseCase[uuid.UUID, frozenset[str]]):
    def __init__(self, user_repository: UserRepository) -> None:
        self._users = user_repository

    def execute(self, request: uuid.UUID) -> frozenset[str]:
        user = self._users.get_by_employee_id(request)
        if user is None:
            return frozenset()
        return user.permission_codes
