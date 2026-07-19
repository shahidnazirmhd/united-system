"""Settings used by the automated test suite (pytest-django).

See backend/pyproject.toml's [tool.pytest.ini_options] for how this file is
selected.
"""
from __future__ import annotations

from .base import *  # noqa: F401,F403

DEBUG = False

# Celery tasks run synchronously, in-process, during tests — a test that
# dispatches a task should observe its effects immediately rather than
# needing a running worker.
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
