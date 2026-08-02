"""Composition root for the Identity module's use cases.

Views should never construct infrastructure classes directly — they call
one of these factory functions, which wires the concrete repositories/ports
into a use case. This is the one file in the module allowed to import both
application-layer use cases and infrastructure-layer implementations
together; keeping that wiring in one place (rather than repeated inline in
every view) is what makes swapping an implementation — e.g. the event bus,
once a real one exists — a one-file change.
"""
from __future__ import annotations

from apps.identity.application.use_cases.activate_user import ActivateUserUseCase
from apps.identity.application.use_cases.assign_role_to_user import AssignRoleToUserUseCase
from apps.identity.application.use_cases.confirm_password_reset import ConfirmPasswordResetUseCase
from apps.identity.application.use_cases.create_role import CreateRoleUseCase
from apps.identity.application.use_cases.create_user import CreateUserUseCase
from apps.identity.application.use_cases.deactivate_user import DeactivateUserUseCase
from apps.identity.application.use_cases.delete_role import DeleteRoleUseCase
from apps.identity.application.use_cases.get_current_user import GetCurrentUserUseCase
from apps.identity.application.use_cases.get_permission_codes_for_employee import (
    GetPermissionCodesForEmployeeUseCase,
)
from apps.identity.application.use_cases.get_role_by_id import GetRoleByIdUseCase
from apps.identity.application.use_cases.get_user_by_id import GetUserByIdUseCase
from apps.identity.application.use_cases.list_permissions import ListPermissionsUseCase
from apps.identity.application.use_cases.list_roles import ListRolesUseCase
from apps.identity.application.use_cases.list_users import ListUsersUseCase
from apps.identity.application.use_cases.login_user import LoginUserUseCase
from apps.identity.application.use_cases.logout_user import LogoutUserUseCase
from apps.identity.application.use_cases.refresh_access_token import RefreshAccessTokenUseCase
from apps.identity.application.use_cases.request_password_reset import RequestPasswordResetUseCase
from apps.identity.application.use_cases.revoke_role_from_user import RevokeRoleFromUserUseCase
from apps.identity.application.use_cases.update_role import UpdateRoleUseCase
from apps.identity.application.use_cases.update_user import UpdateUserUseCase
from apps.identity.infrastructure.email_sender import LoggingEmailSender
from apps.identity.infrastructure.jwt_service import PyJWTTokenService
from apps.identity.infrastructure.password_hasher import DjangoPasswordHasher
from apps.identity.infrastructure.repositories import (
    DjangoPasswordResetTokenRepository,
    DjangoPermissionRepository,
    DjangoRoleRepository,
    DjangoUserRepository,
)
from apps.identity.infrastructure.token_blocklist import RedisTokenBlocklist
from shared_kernel.infrastructure.django_unit_of_work import DjangoUnitOfWork
from shared_kernel.infrastructure.event_bus_impl import event_bus

# EmployeeLookupAdapter import (Phase 7) removed along with the Telegram
# use cases below that were its only caller — Identity no longer looks up
# Employee data for any reason. See apps/employees/interface/identity_adapter.py
# (deleted) and this refactor's delivery notes.


def build_login_use_case() -> LoginUserUseCase:
    return LoginUserUseCase(
        user_repository=DjangoUserRepository(),
        password_hasher=DjangoPasswordHasher(),
        token_service=PyJWTTokenService(),
        unit_of_work=DjangoUnitOfWork(),
        event_bus=event_bus,
    )


def build_logout_use_case() -> LogoutUserUseCase:
    return LogoutUserUseCase(
        token_service=PyJWTTokenService(),
        token_blocklist=RedisTokenBlocklist(),
        event_bus=event_bus,
    )


def build_refresh_use_case() -> RefreshAccessTokenUseCase:
    return RefreshAccessTokenUseCase(
        user_repository=DjangoUserRepository(),
        token_service=PyJWTTokenService(),
        token_blocklist=RedisTokenBlocklist(),
    )


def build_get_current_user_use_case() -> GetCurrentUserUseCase:
    return GetCurrentUserUseCase(user_repository=DjangoUserRepository())


def build_create_user_use_case() -> CreateUserUseCase:
    return CreateUserUseCase(
        user_repository=DjangoUserRepository(),
        password_hasher=DjangoPasswordHasher(),
        unit_of_work=DjangoUnitOfWork(),
    )


def build_list_users_use_case() -> ListUsersUseCase:
    return ListUsersUseCase(user_repository=DjangoUserRepository())


def build_get_user_by_id_use_case() -> GetUserByIdUseCase:
    return GetUserByIdUseCase(user_repository=DjangoUserRepository())


def build_get_permission_codes_for_employee_use_case() -> GetPermissionCodesForEmployeeUseCase:
    """Public entry point for `apps.approvals`'s `ApprovalAuthorizationPort`
    adapter — see that class's docstring for why this is the one
    cross-module call it's allowed to make into Identity."""
    return GetPermissionCodesForEmployeeUseCase(user_repository=DjangoUserRepository())


def build_update_user_use_case() -> UpdateUserUseCase:
    return UpdateUserUseCase(user_repository=DjangoUserRepository(), unit_of_work=DjangoUnitOfWork())


def build_activate_user_use_case() -> ActivateUserUseCase:
    return ActivateUserUseCase(user_repository=DjangoUserRepository(), unit_of_work=DjangoUnitOfWork())


def build_deactivate_user_use_case() -> DeactivateUserUseCase:
    return DeactivateUserUseCase(user_repository=DjangoUserRepository(), unit_of_work=DjangoUnitOfWork())


def build_create_role_use_case() -> CreateRoleUseCase:
    return CreateRoleUseCase(
        role_repository=DjangoRoleRepository(),
        permission_repository=DjangoPermissionRepository(),
        unit_of_work=DjangoUnitOfWork(),
    )


def build_list_roles_use_case() -> ListRolesUseCase:
    return ListRolesUseCase(role_repository=DjangoRoleRepository())


def build_get_role_by_id_use_case() -> GetRoleByIdUseCase:
    return GetRoleByIdUseCase(role_repository=DjangoRoleRepository())


def build_update_role_use_case() -> UpdateRoleUseCase:
    return UpdateRoleUseCase(
        role_repository=DjangoRoleRepository(),
        permission_repository=DjangoPermissionRepository(),
        unit_of_work=DjangoUnitOfWork(),
    )


def build_delete_role_use_case() -> DeleteRoleUseCase:
    return DeleteRoleUseCase(role_repository=DjangoRoleRepository(), unit_of_work=DjangoUnitOfWork())


def build_list_permissions_use_case() -> ListPermissionsUseCase:
    return ListPermissionsUseCase(permission_repository=DjangoPermissionRepository())


def build_assign_role_use_case() -> AssignRoleToUserUseCase:
    return AssignRoleToUserUseCase(
        user_repository=DjangoUserRepository(),
        role_repository=DjangoRoleRepository(),
        unit_of_work=DjangoUnitOfWork(),
        event_bus=event_bus,
    )


def build_revoke_role_use_case() -> RevokeRoleFromUserUseCase:
    return RevokeRoleFromUserUseCase(
        user_repository=DjangoUserRepository(),
        unit_of_work=DjangoUnitOfWork(),
        event_bus=event_bus,
    )


def build_request_password_reset_use_case() -> RequestPasswordResetUseCase:
    return RequestPasswordResetUseCase(
        user_repository=DjangoUserRepository(),
        reset_token_repository=DjangoPasswordResetTokenRepository(),
        email_sender=LoggingEmailSender(),
        unit_of_work=DjangoUnitOfWork(),
        event_bus=event_bus,
    )


def build_confirm_password_reset_use_case() -> ConfirmPasswordResetUseCase:
    return ConfirmPasswordResetUseCase(
        user_repository=DjangoUserRepository(),
        reset_token_repository=DjangoPasswordResetTokenRepository(),
        password_hasher=DjangoPasswordHasher(),
        unit_of_work=DjangoUnitOfWork(),
        event_bus=event_bus,
    )


# build_request_telegram_link_use_case/build_verify_telegram_link_use_case/
# build_unlink_telegram_use_case/build_get_telegram_link_status_use_case
# (Phase 7) removed along with the use cases and repositories they wired —
# equivalent factory functions now live in
# apps/employees/interface/dependencies.py.
