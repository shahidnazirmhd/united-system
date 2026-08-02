"""The generic "who is making this request" contract used by every module's
permission checks.

This lives in shared_kernel rather than apps/identity because every future
module's interface layer (Employee, Leave, Payroll, ...) needs to answer
"is this caller authorized" without importing apps.identity's internals —
depending on identity's concrete classes from every other module would be
exactly the kind of cross-module coupling the architecture forbids
(HRMS_Architecture.md section 1.3: modules depend on published interfaces,
never on another module's internals). apps.identity's authentication class
is the one thing that constructs instances of this; everything else only
ever reads from it.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    user_id: uuid.UUID
    email: str
    role_names: frozenset[str] = field(default_factory=frozenset)
    permission_codes: frozenset[str] = field(default_factory=frozenset)

    @property
    def is_authenticated(self) -> bool:
        # DRF's IsAuthenticated permission checks `request.user.is_authenticated`.
        # A constructed AuthenticatedPrincipal always represents a successfully
        # authenticated caller — there is no "anonymous" instance of this class;
        # an unauthenticated request simply has request.user = None (see
        # UNAUTHENTICATED_USER = None in config/settings/base.py).
        return True

    @property
    def pk(self) -> uuid.UUID:
        # DRF's UserRateThrottle (rest_framework.throttling — the base class
        # behind shared_kernel/api/throttling.py's StandardUserRateThrottle,
        # which every view uses by default via DEFAULT_THROTTLE_CLASSES)
        # builds its per-user cache key from `request.user.pk`, unconditionally,
        # for every authenticated request — it assumes request.user is a
        # django.contrib.auth model instance. This project deliberately has
        # no such model (see apps/identity's module docstring), so without
        # this property every authenticated request would raise
        # AttributeError the moment throttling actually runs against a live
        # server. Static checks (py_compile, import-resolution) can't catch
        # this class of bug — it only surfaces by actually executing a
        # request through DRF's real throttle codepath, which is how it was
        # first found. `is_authenticated` above exists for the identical
        # reason: emulating just enough of Django's user-object surface for
        # framework internals that assume it, without pulling in
        # django.contrib.auth itself.
        return self.user_id

    def has_role(self, role_name: str) -> bool:
        return role_name in self.role_names

    def has_permission(self, permission_code: str) -> bool:
        return permission_code in self.permission_codes
