"""Value objects for the Identity module's domain layer.

`Email` moved to shared_kernel/domain/value_objects.py in Phase 6, once
apps/employees needed the identical validation/normalization for
`work_email`/`personal_email` — re-exported here so every existing import
of `from apps.identity.domain.value_objects import Email` throughout this
module keeps working unchanged; nothing else in identity had to change.

HashedPassword is deliberately not modeled as a value object — a password
hash is an opaque string produced entirely by the PasswordHasherPort
(application/ports.py); giving it its own type would add a wrapper with no
behaviour, since hashing/verification logic already lives behind that port.
"""
from __future__ import annotations

from shared_kernel.domain.value_objects import Email

__all__ = ["Email"]
