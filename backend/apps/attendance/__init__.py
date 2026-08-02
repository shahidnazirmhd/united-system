"""Attendance module: starts with Holiday Management only (round 14 brief
item 5 — "The main Attendance functionality will be implemented later").

Structured identically to Employees' Department Management (same
domain/application/infrastructure/interface layering, same CRUD shape) —
`Holiday` is this module's first entity for exactly the same reason
`Department` was Employees' first supporting entity: something a bigger,
not-yet-built feature (real attendance tracking) will eventually reference,
built now because a nearer-term consumer (Leave's working-day calculation,
round 14 item 6) needs it today.

Owns nothing about how holiday dates are used — that meaning lives in the
consuming module, which reads this module's public service through its own
port/adapter (see apps/leave/application/ports.py's HolidayLookupPort),
exactly like every other cross-module dependency in this codebase.
"""
