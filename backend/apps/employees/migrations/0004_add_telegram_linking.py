"""Employee & Telegram Authentication refactor.

Adds `EmployeeRecord.telegram_user_id`/`telegram_chat_id`/
`telegram_username`/`telegram_linked_at`, plus the new
`employees_link_tokens` table — the Employee-module-owned replacement for
Identity's dropped `identity_telegram_accounts`/`identity_telegram_link_tokens`
(see apps/identity/migrations/0004_drop_telegram_tables.py).

Hand-written, same discipline as every other migration in this project.
Run `python manage.py makemigrations --check` after pulling this into an
environment with dependencies installed, as a final confirmation that
infrastructure/models.py and this migration agree.
"""
from __future__ import annotations

import django.db.models.deletion
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
    dependencies = [
        ("employees", "0003_seed_default_departments"),
    ]

    operations = [
        migrations.AddField(
            model_name="employeerecord",
            name="telegram_user_id",
            field=models.BigIntegerField(blank=True, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="employeerecord",
            name="telegram_chat_id",
            field=models.BigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="employeerecord",
            name="telegram_username",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name="employeerecord",
            name="telegram_linked_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddIndex(
            model_name="employeerecord",
            index=models.Index(fields=["telegram_user_id"], name="employees_telegram_tguid_idx"),
        ),
        migrations.CreateModel(
            name="EmployeeLinkTokenRecord",
            fields=[
                *_base_fields(),
                ("token", models.CharField(max_length=64, unique=True)),
                ("telegram_user_id", models.BigIntegerField()),
                ("chat_id", models.BigIntegerField()),
                ("telegram_username", models.CharField(blank=True, max_length=100, null=True)),
                ("expires_at", models.DateTimeField()),
                ("used_at", models.DateTimeField(blank=True, null=True)),
                (
                    "employee",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="link_tokens",
                        to="employees.employeerecord",
                    ),
                ),
            ],
            options={"db_table": "employees_link_tokens"},
        ),
    ]
