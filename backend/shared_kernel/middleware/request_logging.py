"""Logs one line per request: method, path, status, duration, request id.

Runs after `RequestIDMiddleware` in MIDDLEWARE (config/settings/base.py) so
the id it logs is always populated. This is the "enterprise logging"
counterpart to `RequestIDMiddleware`'s correlation id — together they're
this phase's concrete "Middleware structure" deliverable.
"""
from __future__ import annotations

import logging
import time

from django.http import HttpRequest, HttpResponse

from shared_kernel.middleware.request_id import get_current_request_id

logger = logging.getLogger("apps.request")


class RequestLoggingMiddleware:
    def __init__(self, get_response) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        started_at = time.monotonic()
        response = self.get_response(request)
        elapsed_ms = (time.monotonic() - started_at) * 1000

        logger.info(
            "%s %s -> %s (%.1fms) [request_id=%s]",
            request.method,
            request.path,
            response.status_code,
            elapsed_ms,
            get_current_request_id(),
        )
        return response
