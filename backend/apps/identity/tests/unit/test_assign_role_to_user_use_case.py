"""Unit tests for AssignRoleToUserUseCase — the core RBAC-mutation use case."""
from __future__ import annotations

import uuid

import pytest

from apps.identity.application.dtos import AssignRoleRequest
from apps.identity.application.use_cases.assign_role_to_user import AssignRoleToUserUseCase
from apps.identity.domain.entities import Role, User
from apps.identity.domain.exceptions import (
    RoleAlreadyAssignedError,
    RoleNotFoundError,
    UserNotFoundError,
)
from apps.identity.domain.value_objects import Email
from shared_kernel.application.event_bus import EventBus
from shared_kernel.application.unit_of_work import UnitOfWork


class FakeUnitOfWork(UnitOfWork):
    def commit(self):
        pass

    def rollback(self):
        pass


class FakeEventBus(EventBus):
    def __init__(self):
        self.published = []

    def publish(self, event):
        self.published.append(event)

    def subscribe(self, event_type, handler):
        pass


class FakeUserRepository:
    def __init__(self, user: User | None, already_has_role: bool = False):
        self._user = user
        self._already_has_role = already_has_role
        self.assigned: list[tuple] = []

    def get_by_id(self, user_id):
        return self._user

    def has_role(self, user_id, role_id):
        return self._already_has_role

    def assign_role(self, user_id, role_id, assigned_by):
        self.assigned.append((user_id, role_id, assigned_by))


class FakeRoleRepository:
    def __init__(self, role: Role | None):
        self._role = role

    def get_by_id(self, role_id):
        return self._role


def _make_user() -> User:
    return User(id=uuid.uuid4(), email=Email("someone@example.com"), password_hash="x")


def _make_role() -> Role:
    return Role(id=uuid.uuid4(), name="Manager")


def test_assign_role_succeeds() -> None:
    user, role = _make_user(), _make_role()
    users = FakeUserRepository(user)
    event_bus = FakeEventBus()

    use_case = AssignRoleToUserUseCase(
        user_repository=users,
        role_repository=FakeRoleRepository(role),
        unit_of_work=FakeUnitOfWork(),
        event_bus=event_bus,
    )

    use_case.execute(AssignRoleRequest(user_id=user.id, role_id=role.id, assigned_by=None))

    assert users.assigned == [(user.id, role.id, None)]
    assert len(event_bus.published) == 1


def test_assign_role_fails_when_user_does_not_exist() -> None:
    role = _make_role()
    use_case = AssignRoleToUserUseCase(
        user_repository=FakeUserRepository(None),
        role_repository=FakeRoleRepository(role),
        unit_of_work=FakeUnitOfWork(),
        event_bus=FakeEventBus(),
    )

    with pytest.raises(UserNotFoundError):
        use_case.execute(AssignRoleRequest(user_id=uuid.uuid4(), role_id=role.id, assigned_by=None))


def test_assign_role_fails_when_role_does_not_exist() -> None:
    user = _make_user()
    use_case = AssignRoleToUserUseCase(
        user_repository=FakeUserRepository(user),
        role_repository=FakeRoleRepository(None),
        unit_of_work=FakeUnitOfWork(),
        event_bus=FakeEventBus(),
    )

    with pytest.raises(RoleNotFoundError):
        use_case.execute(AssignRoleRequest(user_id=user.id, role_id=uuid.uuid4(), assigned_by=None))


def test_assign_role_fails_when_already_assigned() -> None:
    user, role = _make_user(), _make_role()
    use_case = AssignRoleToUserUseCase(
        user_repository=FakeUserRepository(user, already_has_role=True),
        role_repository=FakeRoleRepository(role),
        unit_of_work=FakeUnitOfWork(),
        event_bus=FakeEventBus(),
    )

    with pytest.raises(RoleAlreadyAssignedError):
        use_case.execute(AssignRoleRequest(user_id=user.id, role_id=role.id, assigned_by=None))
