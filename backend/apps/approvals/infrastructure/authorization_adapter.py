"""Adapter implementing `apps.approvals.application.ports.ApprovalAuthorizationPort`
against `apps.identity`'s already-composed public use case.

This is the one file in this module allowed to import `apps.identity` —
and even here, only its public composition root
(`apps.identity.interface.dependencies.build_get_permission_codes_for_employee_use_case`),
never its infrastructure repositories or ORM models directly. Same
discipline as `employee_lookup_adapter.py`'s `EmployeeServiceLookupAdapter`
just pointed at Identity instead of Employees — calling into another
module's public application API is the correct cross-module boundary in a
modular monolith, not a violation of "always keep modules independent."
"""
from __future__ import annotations

import uuid

from apps.approvals.application.ports import ApprovalAuthorizationPort
from apps.identity.interface import dependencies as identity_dependencies


class IdentityAuthorizationAdapter(ApprovalAuthorizationPort):
    def get_permission_codes_for_employee(self, employee_id: uuid.UUID) -> frozenset[str]:
        return identity_dependencies.build_get_permission_codes_for_employee_use_case().execute(employee_id)
