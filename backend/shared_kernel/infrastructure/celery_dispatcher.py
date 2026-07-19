"""Thin wrapper for dispatching Celery tasks from application-layer use cases.

Use cases call `dispatch(some_task, ...)` rather than `some_task.delay(...)`
directly, so the fact that background execution is implemented with Celery
specifically (rather than, say, RQ) stays an infrastructure detail the
application layer doesn't hard-depend on syntactically.
"""
from __future__ import annotations

from typing import Any, Callable


def dispatch(task: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    return task.delay(*args, **kwargs)
