"""Phase 7: adds `identity.telegram_accounts` and
`identity.telegram_link_tokens`, per HRMS_Database_Design.md section 3.1
(already approved in Phase 3, not implemented until now — Telegram linking
is the first feature that needs them).

Hand-written, same discipline as every other migration in this project:
cross-checked field-by-field against infrastructure/models.py. Run
`python manage.py makemigrations --check` after pulling this into an
environment with dependencies installed, as a final confirmation.
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
        ("identity", "0002_seed_system_roles"),
    ]

    operations = [
        migrations.CreateModel(
            name="TelegramAccountRecord",
            fields=[
                *_base_fields(),
                ("telegram_user_id", models.BigIntegerField(unique=True)),
                ("telegram_username", models.CharField(blank=True, max_length=100, null=True)),
                ("chat_id", models.BigIntegerField()),
                ("is_active", models.BooleanField(default=True)),
                ("linked_at", models.DateTimeField()),
                ("unlinked_at", models.DateTimeField(blank=True, null=True)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="telegram_account",
                        to="identity.userrecord",
                    ),
                ),
            ],
            options={"db_table": "identity_telegram_accounts"},
        ),
        migrations.CreateModel(
            name="TelegramLinkTokenRecord",
            fields=[
                *_base_fields(),
                ("token", models.CharField(max_length=64, unique=True)),
                ("expires_at", models.DateTimeField()),
                ("used_at", models.DateTimeField(blank=True, null=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="telegram_link_tokens",
                        to="identity.userrecord",
                    ),
                ),
            ],
            options={"db_table": "identity_telegram_link_tokens"},
        ),
        migrations.AddIndex(
            model_name="telegramaccountrecord",
            index=models.Index(fields=["telegram_user_id"], name="identity_telegram_tguid_idx"),
        ),
    ]
