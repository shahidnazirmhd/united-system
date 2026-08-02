"""Initial migration for the Settings module.

Hand-written, same discipline as apps/leave/migrations/0001_initial.py: no
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
            name="SettingRecord",
            fields=[
                *_base_fields(),
                ("key", models.CharField(max_length=100, unique=True)),
                ("value", models.JSONField()),
                ("description", models.CharField(blank=True, default="", max_length=255)),
            ],
            options={
                "db_table": "app_settings",
            },
        ),
    ]
