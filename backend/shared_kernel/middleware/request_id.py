"""Assigns (or propagates) a correlation id for every request.

This is the concrete plumbing behind `audit_log.request_id`
(HRMS_Database_Design.md section 4) — every future module's audit-logging
code can read the current request id via `get_current_request_id()` without
threading it through every function call as an explicit parameter, and
without depending on Django's `request` object being reachable from deep
inside the application/domain layers (which would violate those layers
staying framework-independent).

Uses `contextvars`, not a plain module-level global or Django's older
thread-local pattern — `contextvars` is the correct primitive for both
threaded (WSGI/gunicorn) and async (ASGI) request handling, so this doesn't
need revisiting if/when the project's ASGI path sees real traffic.
"""
from __future__ import annotations

import uuid
from contextvars import ContextVar

from django.http import HttpRequest, HttpResponse

_request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

REQUEST_ID_HEADER = "X-Request-ID"


def get_current_request_id() -> str | None:
    return _request_id_var.get()


class RequestIDMiddleware:
    """Reads `X-Request-ID` from the incoming request if the caller (e.g.
    the future Telegram Gateway, or an upstream load balancer) already
    supplied one, otherwise generates a fresh UUID4. Always echoes it back
    on the response header, and clears the contextvar after the request so
    it can never leak between requests sharing a worker.
    """

    def __init__(self, get_response) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        incoming = request.headers.get(REQUEST_ID_HEADER)
        request_id = incoming or str(uuid.uuid4())
        token = _request_id_var.set(request_id)
        # Also stashed directly on the request object, for code that already
        # has `request` in hand and would rather not import this module.
        request.request_id = request_id  # type: ignore[attr-defined]
        try:
            response = self.get_response(request)
        finally:
            _request_id_var.reset(token)
        response[REQUEST_ID_HEADER] = request_id
        return response
