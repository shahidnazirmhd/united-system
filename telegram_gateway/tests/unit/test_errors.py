"""Unit tests for errors.py — the single lookup table translating backend
error codes / local GatewayErrors into employee-facing Telegram text.

Employee & Telegram Authentication refactor: the error-code vocabulary is
now apps.employees.domain.exceptions's codes exclusively (this Gateway
never talks to apps.identity) — see errors.py's updated _FRIENDLY_MESSAGES
comment. NoLinkedSessionError is gone along with auth/session.py, the only
thing that ever raised it.
"""
from __future__ import annotations

from src.errors import (
    HRMSAPIError,
    LinkingInProgressConflictError,
    NoLinkingInProgressError,
    TelegramAPIError,
    friendly_message_for,
)


def test_known_hrms_error_code_maps_to_specific_friendly_text():
    error = HRMSAPIError(status_code=404, code="employee_not_found", message="No employee found.")
    assert "couldn't find an employee" in friendly_message_for(error)


def test_unknown_hrms_error_code_falls_back_to_default_never_the_raw_backend_message():
    # `message` deliberately looks like something unsafe to show verbatim
    # (e.g. what a raw httpx transport-error string could look like) — the
    # point of this test is that friendly_message_for never surfaces it,
    # regardless of what it says, for any code not in _FRIENDLY_MESSAGES.
    error = HRMSAPIError(
        status_code=400, code="some_new_backend_code", message="[Errno 111] Connection refused at 10.0.0.4:5432"
    )
    assert friendly_message_for(error) == "Something went wrong on our end. Please try again in a moment."


def test_unknown_hrms_error_code_with_no_message_falls_back_to_default():
    error = HRMSAPIError(status_code=500, code="some_new_backend_code", message="")
    assert friendly_message_for(error) == "Something went wrong on our end. Please try again in a moment."


def test_backend_unreachable_never_leaks_the_raw_transport_error():
    # This is the exact scenario the safety fix targets: api_client/hrms_client.py
    # raises HRMSAPIError(code="backend_unreachable", message=str(httpx_exc)) —
    # a raw, technical transport error string, not backend-crafted text.
    error = HRMSAPIError(
        status_code=503, code="backend_unreachable", message="ConnectError: [Errno 111] Connection refused"
    )
    friendly = friendly_message_for(error)
    assert "Errno" not in friendly
    assert "Connection refused" not in friendly
    assert "HR system" in friendly


def test_too_many_otp_attempts_prompts_to_link_again():
    error = HRMSAPIError(status_code=422, code="too_many_otp_attempts", message="Locked.")
    assert "/link" in friendly_message_for(error)


def test_employee_already_linked_to_telegram_prompts_to_unlink_or_contact_hr():
    error = HRMSAPIError(status_code=409, code="employee_already_linked_to_telegram", message="Already linked.")
    friendly = friendly_message_for(error)
    assert "/unlink" in friendly
    assert "HR" in friendly


def test_email_delivery_failed_prompts_to_retry():
    error = HRMSAPIError(status_code=502, code="email_delivery_failed", message="SMTP down.")
    assert "/link" in friendly_message_for(error)


def test_no_linking_in_progress_error_prompts_to_link():
    assert "/link" in friendly_message_for(NoLinkingInProgressError())


def test_linking_in_progress_conflict_does_not_prompt_to_link_again():
    # Deliberately different from NoLinkingInProgressError's message — a
    # conflict means "wait/retry," not "start over."
    message = friendly_message_for(LinkingInProgressConflictError())
    assert "in progress" in message


def test_telegram_api_error_uses_generic_message():
    assert friendly_message_for(TelegramAPIError("boom")) == "Something went wrong on our end. Please try again in a moment."


def test_expired_otp_message_mentions_link_again():
    error = HRMSAPIError(status_code=422, code="expired_employee_link_otp", message="Expired.")
    assert "/link" in friendly_message_for(error)


def test_invalid_otp_message_does_not_leak_backend_wording():
    error = HRMSAPIError(
        status_code=422,
        code="invalid_employee_link_otp",
        message="The provided OTP is invalid or has already been used.",
    )
    friendly = friendly_message_for(error)
    assert friendly != error.message
    assert "code" in friendly.lower()


def test_employee_not_linked_prompts_to_link():
    error = HRMSAPIError(status_code=404, code="employee_not_linked_to_telegram", message="Not linked.")
    assert "/link" in friendly_message_for(error)


def test_duplicate_telegram_link_prompts_to_unlink_first():
    error = HRMSAPIError(status_code=409, code="duplicate_telegram_link", message="Already linked.")
    assert "/unlink" in friendly_message_for(error)
