"""Logging helpers shared by every module's application/infrastructure code.

`config/settings/base.py` already routes any logger under the `apps` or
`shared_kernel` namespace to the console handler at LOG_LEVEL — see the
LOGGING dict there. `get_logger` is a thin, deliberate wrapper (not a bare
`logging.getLogger(__name__)` call scattered through every file) so that
namespace convention is enforced in one place rather than trusted to every
call site to get right.
"""
from __future__ import annotations

import logging
import time
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def log_execution(logger: logging.Logger) -> Callable[[F], F]:
    """Decorator for application-layer entry points (use case `execute()`
    methods, service methods) that logs start, successful completion with
    timing, and failure with the exception — the concrete "enterprise
    logging" every future module's command/query services can opt into with
    one line, rather than hand-writing the same try/except/log around every
    method.

    Deliberately does not swallow or transform the exception — it re-raises
    unchanged so shared_kernel/api/exception_handler.py still makes the
    HTTP-status decision, matching "no exception-to-HTTP-status translation
    outside the exception handler."
    """

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            qualified_name = f"{func.__qualname__}"
            started_at = time.monotonic()
            logger.debug("%s: started", qualified_name)
            try:
                result = func(*args, **kwargs)
            except Exception:
                elapsed_ms = (time.monotonic() - started_at) * 1000
                logger.exception("%s: failed after %.1fms", qualified_name, elapsed_ms)
                raise
            elapsed_ms = (time.monotonic() - started_at) * 1000
            logger.info("%s: completed in %.1fms", qualified_name, elapsed_ms)
            return result

        return wrapper  # type: ignore[return-value]

    return decorator
