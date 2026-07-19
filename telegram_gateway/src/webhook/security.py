"""Verifies Telegram's secret-token header on every request before anything
else runs — per HRMS_Folder_Structure.md section 3.1, "rejecting forged
webhook calls at the door."

This is Telegram's actual, documented security mechanism (not a
project-invented placeholder): `setWebhook` is called once with a
`secret_token`, and Telegram echoes it back as
`X-Telegram-Bot-Api-Secret-Token` on every subsequent call to the webhook
URL. Anyone who doesn't know that secret — including someone who has merely
learned the webhook URL, which is not itself confidential — gets rejected
here, before the request body is even parsed.
"""
from __future__ import annotations

import hmac

from src.errors import InvalidWebhookSignatureError


def verify_webhook_secret(header_value: str | None, expected_secret: str) -> None:
    """Raises InvalidWebhookSignatureError unless `header_value` matches
    `expected_secret` exactly. Uses a constant-time comparison
    (`hmac.compare_digest`) so response timing can't be used to brute-force
    the secret byte by byte — the same discipline used for comparing
    password hashes."""
    if header_value is None or not hmac.compare_digest(header_value, expected_secret):
        raise InvalidWebhookSignatureError()
