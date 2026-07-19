"""UUIDv7 (time-ordered UUID) generation for primary keys.

HRMS_Database_Design.md specifies UUIDv7 — not v4 — as the primary key
strategy for insert-heavy tables, so B-tree index locality stays good under
sustained write load while keeping the benefits of UUIDs over auto-increment
integers (client-generatable, non-sequential, doesn't leak row-count via API
responses). Generated here application-side via the `uuid6` package rather
than a PostgreSQL-side `uuid_generate_v7()` function, which keeps the schema
portable across PostgreSQL versions/extensions instead of depending on a
custom SQL function or PG18+ native support.
"""
from __future__ import annotations

import uuid

from uuid6 import uuid7


def generate_uuid7() -> uuid.UUID:
    return uuid7()
