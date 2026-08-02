"""Project-wide pytest fixtures — this file sits at the pytest rootdir
(alongside pyproject.toml), so it applies to every test under both
`testpaths` (`apps/`, `tests/`) without needing to be imported anywhere.
"""
from __future__ import annotations

import pytest
from django.core.cache import cache


@pytest.fixture
def zero_permission_role():
    """A throwaway custom role with zero permissions granted — for any test,
    in any app, that needs a logged-in `User` who holds *some* role (proving
    a permission check fails on the merits, not just because the caller has
    no role at all) without depending on any specific permission being
    absent from it.

    Before the Role & Permission Management phase, tests across
    apps/employees, apps/leave, and apps/approvals all reused the seeded
    "Employee" system role for this — it happened to hold zero permissions
    by design (see the old apps/identity/migrations/0002_seed_system_roles.py
    comment: "Only HR Admin gets identity-administration permissions... the
    other four are business-facing roles"). That role was deliberately
    removed as a built-in by
    apps/identity/migrations/0006_rename_admin_role_and_prune_system_roles.py
    — only "Admin" ships seeded now, every other role (including one shaped
    like the old "Employee") is created through the real Role Management API,
    never assumed to pre-exist in a fresh test database. Rather than
    resurrect a seeded placeholder role solely so old tests keep working,
    those tests create their own throwaway role via this fixture — exactly
    what a real Admin would do to model "an ordinary employee with no
    special grants" going forward.

    `get_or_create` keeps this idempotent within a single test's transaction
    if more than one fixture in that test happens to request it.
    """
    from apps.identity.infrastructure.models import RoleRecord

    role, _ = RoleRecord.objects.get_or_create(
        name="Test Zero-Permission Role",
        defaults={
            "description": "Test-only role granted no permissions — see this fixture's docstring.",
            "is_system_role": False,
        },
    )
    return role


@pytest.fixture(autouse=True)
def _reset_throttle_cache():
    """DRF's `UserRateThrottle` subclasses (see shared_kernel/api/throttling.py
    — `StandardUserRateThrottle`/`AuthUserRateThrottle`/`TelegramLinkRateThrottle`)
    store their per-IP/per-user request counters in Django's cache framework.
    This project's cache backend is real Redis (`CACHES["default"]`, see
    config/settings/base.py) — a long-lived service shared across the whole
    docker-compose stack, not an in-memory cache pytest-django resets for
    free the way it resets the database per test via the `django_db`
    fixture. Left alone, throttle counters accumulate across every test
    function in the run (and across separate `pytest` invocations against
    the same Redis instance), so a scope with a tight budget — `"telegram"`
    is 10/min, deliberately strict since it gates OTP brute-forcing — gets
    exhausted by early tests and starts failing unrelated, later tests with
    429s that have nothing to do with what those tests are actually
    checking. Clearing before and after every test keeps each test's
    throttle state isolated, the same guarantee `django_db` already gives
    the database.
    """
    cache.clear()
    yield
    cache.clear()
