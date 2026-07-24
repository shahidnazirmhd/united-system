"""Idempotent bootstrap for a TEMPORARY demo deployment — see
DEPLOYMENT_DEMO_GUIDE.md at the repo root.

Why this exists: `create_admin_user` (this same folder) already does the
"create the first HR Admin" half of this, but it's a one-shot interactive
command meant to be run via a shell — and Render's free tier (the guide's
target host) gives neither SSH/shell access nor a pre-deploy-command hook
(both are paid-only features there). The only code Render's free tier lets
us run is the container's own start command. So
`infra/docker/backend.render.Dockerfile` chains `migrate` -> this command
-> gunicorn on every boot instead, which means this command MUST be safe to
run repeatedly (container restarts, redeploys) without erroring or
duplicating data — hence get_or_create/catch-duplicate below, and silently
doing nothing rather than failing if its env vars aren't set.

Not part of this app's real bootstrap path for an actual production
rollout — a deployment with real shell/pre-deploy access should keep using
`create_admin_user` directly and create Departments through whatever
process HR actually settles on (there's no Department REST API yet — see
apps/employees/infrastructure/models.py's DepartmentRecord docstring).

Configuration entirely via env vars (no interactive prompts — this runs
unattended at container boot):
    DEMO_ADMIN_EMAIL, DEMO_ADMIN_PASSWORD        (required to seed the admin)
    DEMO_DEPARTMENT_NAME, DEMO_DEPARTMENT_CODE   (default: "Demo", "DEMO")
"""
from __future__ import annotations

import os

from django.core.management.base import BaseCommand

from apps.identity.application.dtos import CreateUserRequest
from apps.identity.application.use_cases.create_user import CreateUserUseCase
from apps.identity.domain.exceptions import DuplicateEmailError
from apps.identity.infrastructure.password_hasher import DjangoPasswordHasher
from apps.identity.infrastructure.repositories import DjangoRoleRepository, DjangoUserRepository
from shared_kernel.infrastructure.django_unit_of_work import DjangoUnitOfWork


class Command(BaseCommand):
    help = "Idempotently seeds a demo Department + HR Admin user from env vars (temporary-deployment bootstrap)."

    def handle(self, *args, **options) -> None:
        self._seed_department()
        self._seed_admin()

    def _seed_department(self) -> None:
        # Imported here, not at module level: this app (identity) has no
        # normal reason to depend on apps.employees, so keeping the import
        # scoped to this one demo-only method avoids implying a real
        # cross-module dependency to anyone skimming this file's imports.
        from apps.employees.infrastructure.models import DepartmentRecord

        code = os.environ.get("DEMO_DEPARTMENT_CODE", "DEMO")
        name = os.environ.get("DEMO_DEPARTMENT_NAME", "Demo")

        department, created = DepartmentRecord.objects.get_or_create(code=code, defaults={"name": name})
        if created:
            self.stdout.write(self.style.SUCCESS(f"Seeded department '{name}' ({code}), id={department.id}"))
        else:
            self.stdout.write(f"Department '{code}' already exists (id={department.id}) — skipped.")

    def _seed_admin(self) -> None:
        email = os.environ.get("DEMO_ADMIN_EMAIL")
        password = os.environ.get("DEMO_ADMIN_PASSWORD")
        if not email or not password:
            self.stdout.write("DEMO_ADMIN_EMAIL/DEMO_ADMIN_PASSWORD not set — skipping admin seed.")
            return

        user_repository = DjangoUserRepository()
        role_repository = DjangoRoleRepository()
        use_case = CreateUserUseCase(
            user_repository=user_repository,
            password_hasher=DjangoPasswordHasher(),
            unit_of_work=DjangoUnitOfWork(),
        )

        try:
            user = use_case.execute(CreateUserRequest(email=email, password=password))
        except DuplicateEmailError:
            self.stdout.write(f"Admin '{email}' already exists — skipped.")
            return

        hr_admin_role = role_repository.get_by_name("HR Admin")
        if hr_admin_role is None:
            self.stdout.write(self.style.WARNING("'HR Admin' role not found — did `migrate` run first?"))
            return

        user_repository.assign_role(user.id, hr_admin_role.id, assigned_by=None)
        self.stdout.write(self.style.SUCCESS(f"Seeded HR Admin '{email}' (id={user.id})."))
