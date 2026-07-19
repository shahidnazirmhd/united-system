"""Structured logging setup for the Telegram Gateway.

Every log line is JSON (one object per line) so it composes with whatever
log aggregation the deployment environment already has, matching the
enterprise logging expectation in the Phase 7 brief. Fields are deliberately
narrow and consistent: `event`, `telegram_user_id` (never the employee's
name/email — that's a backend concern, not this service's to echo into
logs), and free-form `**context`.

Secrets (OTPs, access/refresh tokens, the webhook secret) are never passed
to these helpers — see `redact` for the one place a caller-supplied context
dict gets defensively scrubbed if a forbidden key slips in, as a last line
of defence rather than the primary control (the primary control is simply
never putting a secret into a log call in the first place).
"""
from __future__ import annotations

import json
import logging
import sys
import time
from typing import Any

_FORBIDDEN_KEYS = {"otp", "access_token", "refresh_token", "token", "webhook_secret_token", "password"}


def redact(context: dict[str, Any]) -> dict[str, Any]:
    return {k: ("***redacted***" if k.lower() in _FORBIDDEN_KEYS else v) for k, v in context.items()}


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        extra = getattr(record, "context", None)
        if extra:
            payload.update(redact(extra))
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    root.addHandler(handler)


def log_event(logger: logging.Logger, level: int, event: str, **context: Any) -> None:
    """The one call site every module in this service uses instead of raw
    `logger.info(f"...")` string formatting — keeps every log line
    structured and greppable by `event` name."""
    logger.log(level, event, extra={"context": {"event": event, **context}})
