"""Dashboard (Phase 14) has no domain layer of its own — deliberately, not
an oversight.

Every other module's domain layer exists to hold *that module's own*
entities, value objects, invariants, and repository abstractions (e.g.
`Employee`, `LeaveRequest`, `ApprovalRequest`). Dashboard owns no such
concept: it is a pure read-aggregator that composes already-computed
statistics from Employees, Leave, and Attendance and hands them to the
frontend. It has no business rules to enforce, no entity lifecycle, and
therefore nothing for a domain layer to protect.

This is also why Dashboard is the first module in this codebase with no
`models.py` and no `migrations/` package — see `config/module_registry.py`'s
docstring for the module list, and `interface/dependencies.py` for how this
module still follows the same Dependency Inversion discipline as every
other one despite having nothing of its own to persist: `application/ports.py`
defines what Dashboard needs (statistics/lookups, in Dashboard's own
vocabulary), and `infrastructure/` adapts each source module's already-public
composition root to satisfy those ports — never touching another module's
ORM models directly.
"""
from __future__ import annotations
