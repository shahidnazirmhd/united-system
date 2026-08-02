"""Initial migration for the Attendance module (Holiday Management only —
see this module's __init__.py docstring).

Hand-written, same discipline as every other module's 0001_initial.py: no
PyPI/network access in this sandbox to run `makemigrations` for real, so
every field here was cross-checked field-by-field against
infrastructure/models.py. Run `python manage.py makemigrations --check`
after pulling this into an environment with dependencies installed, as a
final confirmation.
"""
from __future__ import annotations

from django.db import migrations, models

import shared_kernel.infrastructure.uuid7


def _base_fields() -> list[tuple[str, object]]:
    return [
        (
            "id",
            models.UUIDField(
                default=shared_kernel.infrastructure.uuid7.generate_uuid7,
                editable=False,
                primary_key=True,
                serialize=False,
            ),
        ),
        ("created_at", models.DateTimeField(auto_now_add=True)),
        ("updated_at", models.DateTimeField(auto_now=True)),
        ("created_by", models.UUIDField(blank=True, null=True)),
        ("updated_by", models.UUIDField(blank=True, null=True)),
    ]


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="HolidayRecord",
            fields=[
                *_base_fields(),
                ("name", models.CharField(max_length=150)),
                ("holiday_date", models.DateField(unique=True)),
                ("description", models.TextField(blank=True, default="")),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={
                "db_table": "attendance_holidays",
                "ordering": ["holiday_date"],
            },
        ),
        migrations.AddIndex(
            model_name="holidayrecord",
            index=models.Index(fields=["holiday_date"], name="attendance_holidays_date_idx"),
        ),
    ]
