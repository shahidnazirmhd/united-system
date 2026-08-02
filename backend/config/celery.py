"""Celery application entrypoint.

`apps.approvals.infrastructure.tasks` (Phase 9) is the first module with a
real background task — routed to its own `approvals` queue below, per
HRMS_Architecture.md section 8 (dedicated queues per workload shape). The
routing pattern every future module's `infrastructure/tasks.py` will use is
documented in the comment further down.

`app.conf.beat_schedule` (round 14) is this codebase's first scheduled
task, requiring a Celery Beat process — see `infra/docker-compose.yml`'s
new `celery_beat` service. No `django-celery-beat` dependency was added:
a single, static, in-code schedule is the right amount of machinery for
one daily job, and this project's existing scheduled-task needs (so far,
just this one) don't call for the DB-backed dynamic scheduling that
package exists for. Revisit if a future module needs schedules editable
at runtime without a redeploy.
"""
from __future__ import annotations

import os

from celery import Celery
from celery.schedules import crontab

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
app.conf.task_routes = {
    "apps.approvals.infrastructure.tasks.*": {"queue": "approvals"},
    "apps.leave.infrastructure.tasks.*": {"queue": "leave"},
}

# Round 14 items 6/8 — daily Employee Current Status reconciliation for
# leave requests approved ahead of their start date, or whose leave period
# has ended. 00:15 server time: after midnight (so "today" has definitely
# rolled over for every request's date comparison) but early enough that
# HR sees an up-to-date status well before the working day starts. See
# apps/leave/infrastructure/tasks.py for the task itself.
app.conf.beat_schedule = {
    "leave-reconcile-employee-statuses": {
        "task": "apps.leave.infrastructure.tasks.reconcile_leave_employee_statuses",
        "schedule": crontab(hour=0, minute=15),
    },
}
