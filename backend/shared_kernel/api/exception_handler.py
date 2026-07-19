"""Custom DRF exception handler.

This is the single place a raised exception — whether a DomainError from the
application layer or an unexpected framework exception — becomes an HTTP
response. No individual view/viewset should catch and translate an exception
itself; doing so would put decision-making back into the interface layer,
which is exactly what "no business logic in views" rules out.
"""
from __future__ import annotations

import logging

from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_default_exception_handler

from shared_kernel.api.exceptions import DomainError
from shared_kernel.api.response import error_response

logger = logging.getLogger(__name__)


def custom_exception_handler(exc: Exception, context: dict) -> Response | None:
    if isinstance(exc, DomainError):
        return error_response(code=exc.code, message=exc.message, status_code=exc.status_code)

    response = drf_default_exception_handler(exc, context)
    if response is not None:
        response.data = {
            "success": False,
            "error": {
                "code": "request_error",
                "message": "The request could not be processed.",
                "details": response.data,
            },
        }
        return response

    logger.exception("Unhandled exception in %s", context.get("view"))
    return error_response(
        code="internal_error",
        message="An unexpected error occurred.",
        status_code=500,
    )
