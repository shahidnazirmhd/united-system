"""Round 14 item 8 — adds `EmployeeRecord.current_status`/
`status_before_leave`. See domain/enums.py EmployeeCurrentStatus's
docstring for why this is a second, separate status field from
`employment_status`.

Hand-written, same discipline as every other migration in this project.
Run `python manage.py makemigrations --check` after pulling this into an
environment with dependencies installed, as a final confirmation that
infrastructure/models.py and this migration agree.
"""
from __future__ import annotations

from django.db import migrations, models

CURRENT_STATUS_CHOICES = [
    ("not_joined", "Not Joined"),
    ("working", "Working"),
    ("sick_leave", "Sick Leave"),
    ("annual_leave", "Annual Leave"),
    ("terminated", "Terminated"),
    ("resigned", "Resigned"),
]


class Migration(migrations.Migration):
    dependencies = [
        ("employees", "0005_add_link_token_attempt_count"),
    ]

    operations = [
        migrations.AddField(
            model_name="employeerecord",
            name="current_status",
            field=models.CharField(choices=CURRENT_STATUS_CHOICES, default="not_joined", max_length=20),
        ),
        migrations.AddField(
            model_name="employeerecord",
            name="status_before_leave",
            field=models.CharField(blank=True, choices=CURRENT_STATUS_CHOICES, max_length=20, null=True),
        ),
        migrations.AddIndex(
            model_name="employeerecord",
            index=models.Index(fields=["current_status"], name="employees_current_status_idx"),
        ),
    ]
