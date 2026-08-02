"""Unit tests for `GetPermissionCodesForEmployeeUseCase` — the read
`apps.approvals`'s `ApprovalAuthorizationPort` adapter calls into Identity
for permission-based approval steps (Phase 13). Hand-rolled fake
repository, no Django, no database.
"""
from __future__ import annotations

import uuid

from apps.identity.application.use_cases.get_permission_codes_for_employee import (
    GetPermissionCodesForEmployeeUseCase,
)
from apps.identity.domain.entities import Role, User
from apps.identity.domain.value_objects import Email


class FakeUserRepository:
    def __init__(self, user_by_employee_id: dict | None = None):
        self._by_employee_id = user_by_employee_id or {}

    def get_by_employee_id(self, employee_id):
        return self._by_employee_id.get(employee_id)


def _make_user(employee_id: uuid.UUID, *, roles: tuple[Role, ...] = ()) -> User:
    return User(id=uuid.uuid4(), email=Email("someone@example.com"), password_hash="x", employee_id=employee_id, roles=roles)


def test_returns_the_linked_users_permission_codes() -> None:
    employee_id = uuid.uuid4()
    role = Role(id=uuid.uuid4(), name="HR Admin", permission_codes=frozenset({"leave.manage_leave", "leave.view_leave"}))
    user = _make_user(employee_id, roles=(role,))
    use_case = GetPermissionCodesForEmployeeUseCase(user_repository=FakeUserRepository({employee_id: user}))

    result = use_case.execute(employee_id)

    assert result == frozenset({"leave.manage_leave", "leave.view_leave"})


def test_returns_empty_frozenset_when_the_employee_has_no_linked_user() -> None:
    use_case = GetPermissionCodesForEmployeeUseCase(user_repository=FakeUserRepository({}))

    result = use_case.execute(uuid.uuid4())

    assert result == frozenset()


def test_returns_empty_frozenset_when_the_linked_user_has_no_roles() -> None:
    employee_id = uuid.uuid4()
    user = _make_user(employee_id, roles=())
    use_case = GetPermissionCodesForEmployeeUseCase(user_repository=FakeUserRepository({employee_id: user}))

    result = use_case.execute(employee_id)

    assert result == frozenset()
