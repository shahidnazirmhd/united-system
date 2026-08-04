"""HR Leave Workflow round, item 1 schema changes:

- `LeaveRequestRecord.level1_skipped` / `.level1_skip_reason` — whether an
  HR-on-behalf application's Level 1 (manager) approval step was
  automatically skipped, and why (see domain/entities.py LeaveRequest's
  matching fields for the full reasoning).
- `LeaveRequestRecord.initiated_via` / `.initiator_user_id` /
  `.initiator_telegram_user_id` — which channel actually submitted the
  request ("hr" / "telegram" / None for ordinary self-service), and who.

All five columns default to their "ordinary self-service, nothing special"
values (`False` / `NULL`), so every pre-existing row backfills correctly
with no data migration needed — a request applied before this column
existed was, by definition, never HR-on-behalf-with-a-skip (that capability
did not exist yet), so `level1_skipped=False` is not just a safe default,
it is the historically correct value.

Hand-written, same discipline as every other migration in this project.
Run `python manage.py makemigrations --check` after pulling this into an
environment with dependencies installed, as a final confirmation.
"""
from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("leave", "0005_working_days_and_status_mapping"),
    ]

    operations = [
        migrations.AddField(
            model_name="leaverequestrecord",
            name="level1_skipped",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="leaverequestrecord",
            name="level1_skip_reason",
            field=models.CharField(blank=True, max_length=40, null=True),
        ),
        migrations.AddField(
            model_name="leaverequestrecord",
            name="initiated_via",
            field=models.CharField(blank=True, max_length=10, null=True),
        ),
        migrations.AddField(
            model_name="leaverequestrecord",
            name="initiator_user_id",
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="leaverequestrecord",
            name="initiator_telegram_user_id",
            field=models.BigIntegerField(blank=True, null=True),
        ),
    ]
