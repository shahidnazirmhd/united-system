"""Approvals module deliberately does not define new permission *classes* —
it reuses Identity's `HasPermission`/`HasRole`, exactly like
`apps.leave.interface.permissions` already does (see that file's docstring
for the full reasoning; not repeated module by module).

What this file adds is this module's own permission *code* constants, kept
in sync with `apps/approvals/migrations/0002_seed_approval_permissions.py`'s
and `apps/approvals/migrations/0006_seed_level_approval_permissions.py`'s
seeded codes.

`LEVEL1_APPROVE`/`LEVEL2_APPROVE` (Approval Workflow Changes v2) are
deliberately engine-level, not Leave-specific — Leave's chain resolver
(`apps.leave.infrastructure.leave_approval_chain_resolver`) does NOT import
these constants directly (that file is infrastructure reaching into this
module's interface layer, which this codebase's layering rule forbids even
across modules — see that file's own "must match X exactly" comment); it
keeps its own local copies of these exact strings instead. They live here,
under `apps.approvals`, so any future subject module adopting the same
generic "level 1 / level 2" two-stage pattern can reuse the same two codes
rather than each module minting its own.
"""
from __future__ import annotations

from apps.identity.interface.permissions import HasPermission, HasRole

VIEW_APPROVALS = "approvals.view_approvals"
DECIDE_APPROVALS = "approvals.decide_approvals"
LEVEL1_APPROVE = "approvals.level1_approve"
LEVEL2_APPROVE = "approvals.level2_approve"

__all__ = [
    "HasPermission",
    "HasRole",
    "VIEW_APPROVALS",
    "DECIDE_APPROVALS",
    "LEVEL1_APPROVE",
    "LEVEL2_APPROVE",
]
