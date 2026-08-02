"""Round 16 item 1 regression tests: `DomainError`'s message resolution
used to fall back to the RAISED exception class's entire docstring
(architectural reasoning paragraphs included) whenever no explicit message
was passed — see `shared_kernel.api.exceptions._first_paragraph`'s
docstring for the full bug. `EmployeeNotEligibleForLeaveError` was the
concrete case reported: raising it with no message dumped a multi-paragraph
internal docstring into the HTTP error envelope, which the HR web frontend
then rendered verbatim as `error.message` (Telegram was insulated by its
own `_FRIENDLY_MESSAGES` lookup, which was separately missing this code —
see telegram_gateway/tests/unit/test_errors.py's matching regression test).
"""
from __future__ import annotations

from apps.leave.domain.exceptions import EmployeeNotEligibleForLeaveError, NoManagerAssignedError


def test_employee_not_eligible_for_leave_message_is_short_and_user_facing() -> None:
    message = EmployeeNotEligibleForLeaveError().message

    assert "Round 14" not in message
    assert "EmployeeLookupPort" not in message
    assert "does not permit applying for leave" in message
    # A `DomainError`'s resolved message is used verbatim as the first line
    # of a multi-line docstring's paragraph, collapsed to one line — no
    # literal newlines from the docstring's own wrapping should survive.
    assert "\n" not in message


def test_no_manager_assigned_message_unaffected_by_first_paragraph_extraction() -> None:
    # This exception's docstring already led with a clean, single-paragraph
    # user-facing sentence before round 16 item 1 — confirms the fix is
    # backward compatible with every exception that was already well-formed.
    message = NoManagerAssignedError().message

    assert message == "No manager is assigned to your account. Please contact HR."
