"""Data migration: seeds the module's first real setting,
`default_week_off` — round 14 brief item 4 ("Add a Default Week Off
setting. Default value should be Sunday.").

Value convention (documented once here, read by every consumer): an
integer 0-6 matching Python's `date.weekday()` — 0=Monday ... 6=Sunday.
Sunday's default is therefore `6`. Read by apps.leave's own
SettingsLookupPort adapter for the working-day calculation (round 14 item
6) — this module has no idea Leave exists; it just stores the value.

"Other settings will be added in future" (round 14 brief) — adding one
means one more `get_or_create` call in a migration like this, never a
schema change (see this module's own docstring for why).
"""
from __future__ import annotations

from django.db import migrations

DEFAULT_SETTINGS = [
    {
        "key": "default_week_off",
        "value": 6,
        "description": "Default weekly day off used for working-day calculations "
        "(0=Monday ... 6=Sunday). Default: Sunday.",
    },
]


def seed_default_settings(apps, schema_editor):
    SettingRecord = apps.get_model("app_settings", "SettingRecord")
    for setting in DEFAULT_SETTINGS:
        SettingRecord.objects.get_or_create(
            key=setting["key"],
            defaults={"value": setting["value"], "description": setting["description"]},
        )


def remove_default_settings(apps, schema_editor):
    SettingRecord = apps.get_model("app_settings", "SettingRecord")
    SettingRecord.objects.filter(key__in=[s["key"] for s in DEFAULT_SETTINGS]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("app_settings", "0002_seed_settings_permissions"),
    ]

    operations = [
        migrations.RunPython(seed_default_settings, remove_default_settings),
    ]
