"""Celery application entrypoint.

Queue routing is left empty on purpose: no module has background tasks yet.
The routing pattern each future module's `infrastructure/tasks.py` will use
is documented here so the convention is established before it's needed,
per HRMS_Architecture.md section 8 (dedicated queues per workload shape).
"""
from __future__ import annotations

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

app = Celery("united_hrms")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# Example of the routing convention future modules will use:
#   app.conf.task_routes = {
#       "apps.payroll.infrastructure.tasks.*": {"queue": "payroll"},
#       "apps.notifications.infrastructure.tasks.*": {"queue": "default"},
#       "apps.*.infrastructure.tasks.generate_report*": {"queue": "reports"},
#   }
app.conf.task_routes = {}
