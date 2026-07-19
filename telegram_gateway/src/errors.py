"""Error hierarchy for the Telegram Gateway.

Two families, kept structurally distinct because they're handled
differently:

1. `GatewayError` and subclasses — problems local to this service (invalid
   webhook signature, no linked session, Telegram API failure). Raised and
   caught entirely within this codebase.
2. `HRMSAPIError` — a structured wrapper around whatever error envelope the
   backend returned (`{"success": false, "error": {"code": ..., "message":
   ...}}`, per shared_kernel/api/exception_handler.py on the Django side).
   `api_client/hrms_client.py` raises this for every non-2xx response;
   handlers never see a raw httpx.Response or parse JSON error shapes
   themselves — that would be business/protocol logic leaking into
   `handlers/`, the same discipline CODING_STANDARD.md enforces against
   Django views, applied here to this service's own "views" (handlers).

`friendly_message_for` is the single place mapping a backend error `code`
(or a local GatewayError) to the Telegram-facing text — one lookup table,
not N handlers each inventing their own copy.
"""
from __future__ import annotations


class GatewayError(Exception):
    """Base class for every error raised inside this service."""


class InvalidWebhookSignatureError(GatewayError):
    """The X-Telegram-Bot-Api-Secret-Token header was missing or wrong."""


class LinkingInProgressConflictError(GatewayError):
    """A new /link was started while another linking flow was already
    awaiting an OTP for this chat."""


class NoLinkingInProgressError(GatewayError):
    """An OTP-shaped message arrived but no /link flow is currently pending
    for this chat — nothing to verify it against."""


class TelegramAPIError(GatewayError):
    """The Telegram Bot API itself returned a non-ok response (send/edit
    message, answer callback query, etc.)."""


class HRMSAPIError(GatewayError):
    """The backend HRMS API returned an error envelope.

    `code` is the backend's own `error.code` (e.g. "employee_not_found",
    "invalid_otp") — the exact same vocabulary apps/identity and
    apps/employees's DomainError subclasses use, so this Gateway's error
    handling stays in lockstep with the backend's without needing its own
    parallel exception taxonomy.
    """

    def __init__(self, *, status_code: int, code: str, message: str) -> None:
        super().__init__(f"HRMS API error ({status_code} {code}): {message}")
        self.status_code = status_code
        self.code = code
        self.message = message


# Keyed by apps.employees.domain.exceptions's `code` values (Employee &
# Telegram Authentication refactor) — this Gateway now only ever talks to
# apps/employees, never apps/identity, so this is the complete vocabulary
# of error codes it can receive. See that module's exceptions.py.
#
# Every entry here MUST be a hand-written, safe-to-show sentence — never a
# format string built from `error.message`. `HRMSAPIError.message` can
# originate from two very different places: a backend DomainError's own
# crafted message (generally fine) or, for backend_unreachable specifically,
# the raw string of a caught httpx exception (e.g. "[Errno 111] Connection
# refused") — not something any real employee should ever see in a chat
# message. `friendly_message_for` below never falls back to `error.message`
# for exactly this reason; every code that can occur must have an entry
# here, or it gets the generic fallback instead of a leak.
_FRIENDLY_MESSAGES: dict[str, str] = {
    "employee_not_found": "We couldn't find an employee with that ID. Please double-check it and try again.",
    "invalid_employee_link_otp": "That code isn't right (or has already been used). Please check your messages "
    "and try again, or send /link to request a new code.",
    "expired_employee_link_otp": "That code has expired. Send /link to request a new one.",
    "too_many_otp_attempts": "That code has been entered incorrectly too many times and is no longer valid. "
    "Send /link to request a new code.",
    "duplicate_telegram_link": "This Telegram account is already linked to a different employee. "
    "Send /unlink first if you want to link a different account.",
    "employee_already_linked_to_telegram": "This employee ID is already linked to a different Telegram "
    "account. If that's you on a new device or phone, ask the previous Telegram account to send /unlink "
    "first. If you no longer have access to it, please contact HR support.",
    "employee_not_linked_to_telegram": "Your Telegram account isn't linked yet. Send /link to get started.",
    "employee_not_active": "This employee record isn't active. Please contact HR.",
    "email_delivery_failed": "We generated your verification code but couldn't email it just now. Please "
    "send /link again in a moment to retry.",
    "backend_unreachable": "We're having trouble reaching the HR system right now. Please try again in a "
    "few minutes.",
    "internal_error": "Something went wrong on our end. Please try again in a moment.",
}

_DEFAULT_FRIENDLY_MESSAGE = "Something went wrong on our end. Please try again in a moment."


def friendly_message_for(error: Exception) -> str:
    """The one place a raw exception becomes the text a real employee reads
    in Telegram — never a stack trace, never a raw backend error code, and
    (deliberately) never the raw `error.message` off an HRMSAPIError either
    — see `_FRIENDLY_MESSAGES`'s docstring for why that fallback would be
    unsafe. Any backend error code this Gateway doesn't recognize gets the
    generic message, not whatever text happened to be attached to it.
    """
    if isinstance(error, HRMSAPIError):
        return _FRIENDLY_MESSAGES.get(error.code, _DEFAULT_FRIENDLY_MESSAGE)
    if isinstance(error, NoLinkingInProgressError):
        return "I wasn't expecting a code right now. Send /link to start linking your account."
    if isinstance(error, LinkingInProgressConflictError):
        return "You already have a linking request in progress. Check your messages for the code, or wait a " \
            "few minutes for it to expire before trying again."
    if isinstance(error, TelegramAPIError):
        return _DEFAULT_FRIENDLY_MESSAGE
    return _DEFAULT_FRIENDLY_MESSAGE
