"""Password hashing, implemented via Django's own hasher utilities.

`django.contrib.auth.hashers` is safe to import without `django.contrib.auth`
in INSTALLED_APPS — it's a pure hashing utility module with no dependency on
the auth app's models being registered. This reuses Django's battle-tested,
configurable PBKDF2 hashing (upgradeable to Argon2 later via the
PASSWORD_HASHERS setting) without pulling in any of Django's auth machinery
this project has deliberately avoided.
"""
from __future__ import annotations

from django.contrib.auth.hashers import check_password, make_password

from apps.identity.application.ports import PasswordHasherPort


class DjangoPasswordHasher(PasswordHasherPort):
    def hash(self, raw_password: str) -> str:
        return make_password(raw_password)

    def verify(self, raw_password: str, password_hash: str) -> bool:
        return check_password(raw_password, password_hash)
