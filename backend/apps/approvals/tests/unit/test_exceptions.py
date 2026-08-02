"""Round 17 item 1 regression test: `ApprovalCallerNotAnEmployeeError`'s
docstring used to lead with "The calling principal is not linked to any
employee record." — accurate, but internal-jargon phrasing that
`DomainError`'s `_first_paragraph` extraction (see
shared_kernel/api/exceptions.py, fixed in round 16 item 1) then surfaced
verbatim as `error.message` to the HR web frontend whenever a User with no
linked Employee tried to decide (approve/reject) an approval. See
`apps.leave.tests.unit.test_exceptions` for the matching round-16 pattern.
"""
from __future__ import annotations

from apps.approvals.domain.exceptions import ApprovalCallerNotAnEmployeeError


def test_caller_not_an_employee_message_is_clean_and_user_facing() -> None:
    message = ApprovalCallerNotAnEmployeeError().message

    assert "calling principal" not in message.lower()
    assert "EmployeeLookupPort" not in message
    assert "not linked to an employee record" in message
    # A `DomainError`'s resolved message is used verbatim as the first line
    # of a multi-line docstring's paragraph, collapsed to one line — no
    # literal newlines from the docstring's own wrapping should survive.
    assert "\n" not in message
