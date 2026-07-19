"""Bootstraps the first HR Admin account.

Necessary because of a chicken-and-egg problem: creating a user via the API
requires the identity.manage_users permission, which requires an existing
HR Admin to grant it. This command is the one way into the system before
any user exists — analogous to Django's own `createsuperuser`, scoped to
this project's own RBAC model instead of Django's.

Location note: this file MUST live at apps/identity/management/commands/ —
Django only auto-discovers management commands directly under
`<app_package>/management/commands/` for each app listed in INSTALLED_APPS
(here, app_package is "apps.identity", matching IdentityConfig.name in
apps.py). It does not search subdirectories such as infrastructure/, which
is where an earlier version of this file mistakenly lived, making it
invisible to `manage.py` entirely.

Usage:
    python manage.py create_admin_user --email admin@example.com --password "..."
"""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.identity.application.dtos import CreateUserRequest
from apps.identity.application.use_cases.create_user import CreateUserUseCase
from apps.identity.domain.exceptions import DuplicateEmailError
from apps.identity.infrastructure.password_hasher import DjangoPasswordHasher
from apps.identity.infrastructure.repositories import DjangoRoleRepository, DjangoUserRepository
from shared_kernel.infrastructure.django_unit_of_work import DjangoUnitOfWork


class Command(BaseCommand):
    help = "Creates the first HR Admin user account."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--email", required=True)
        parser.add_argument("--password", required=True)

    def handle(self, *args, **options) -> None:
        user_repository = DjangoUserRepository()
        role_repository = DjangoRoleRepository()

        use_case = CreateUserUseCase(
            user_repository=user_repository,
            password_hasher=DjangoPasswordHasher(),
            unit_of_work=DjangoUnitOfWork(),
        )

        try:
            user = use_case.execute(
                CreateUserRequest(email=options["email"], password=options["password"])
            )
        except DuplicateEmailError as exc:
            raise CommandError(str(exc)) from exc

        hr_admin_role = role_repository.get_by_name("HR Admin")
        if hr_admin_role is None:
            raise CommandError(
                "The 'HR Admin' system role does not exist — run "
                "`python manage.py migrate` first (it's seeded by migration 0002)."
            )

        user_repository.assign_role(user.id, hr_admin_role.id, assigned_by=None)

        self.stdout.write(
            self.style.SUCCESS(f"Created HR Admin user '{user.email}' (id={user.id}).")
        )
