"""Settings module: a generic, key-value application-settings store.

Deliberately NOT one hand-written Django field per setting. The very first
requirement this module ships with (Default Week Off) is already a strong
signal that more settings are coming ("Other settings will be added in
future" — round 14 brief) — a schema migration for every new setting would
violate the same "new capability should mean new code, not edits to
existing modules" principle every other module in this codebase already
follows (see config/module_registry.py's docstring). Instead:
`SettingRecord(key unique, value JSONField, description)` — adding a new
setting is a one-row data migration, never a schema change.

Owns nothing about *how* a setting is used (e.g. "default_week_off drives
Leave's working-day calculation") — that meaning lives entirely in the
consuming module, which reads this module's public service through its own
port/adapter (see apps/leave/application/ports.py's SettingsLookupPort),
exactly like every other cross-module dependency in this codebase.
"""
