"""Unit tests for webhook/security.py — the webhook signature check that
must reject forged calls before anything else runs."""
from __future__ import annotations

import pytest

from src.errors import InvalidWebhookSignatureError
from src.webhook.security import verify_webhook_secret


def test_matching_secret_passes_silently():
    verify_webhook_secret("correct-secret", "correct-secret")  # does not raise


def test_missing_header_is_rejected():
    with pytest.raises(InvalidWebhookSignatureError):
        verify_webhook_secret(None, "correct-secret")


def test_wrong_secret_is_rejected():
    with pytest.raises(InvalidWebhookSignatureError):
        verify_webhook_secret("wrong-secret", "correct-secret")


def test_empty_string_secret_is_rejected():
    with pytest.raises(InvalidWebhookSignatureError):
        verify_webhook_secret("", "correct-secret")
