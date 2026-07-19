"""DRF serializers for Identity.

Pure protocol translation (JSON <-> application-layer DTOs) — no validation
here beyond shape/type checking (is this a valid email format, is this
field present). Business validation (does this email belong to an active
account, is this password correct, does this role already exist) happens in
the domain/application layers and surfaces back as a DomainError, which
shared_kernel/api/exception_handler.py turns into the standard error
envelope. See CODING_STANDARD.md: "no business logic in views" — the same
discipline applies here, one layer further out.
"""
from __future__ import annotations

from rest_framework import serializers


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)


class TokenPairResponseSerializer(serializers.Serializer):
    access_token = serializers.CharField()
    refresh_token = serializers.CharField()
    token_type = serializers.CharField()
    expires_in = serializers.IntegerField()


class RefreshSerializer(serializers.Serializer):
    refresh_token = serializers.CharField()


class LogoutSerializer(serializers.Serializer):
    refresh_token = serializers.CharField()


class RoleSummarySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()


class UserSummarySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    email = serializers.EmailField()
    is_active = serializers.BooleanField()
    is_system_account = serializers.BooleanField()
    employee_id = serializers.UUIDField(allow_null=True)
    roles = RoleSummarySerializer(many=True)
    permission_codes = serializers.ListField(child=serializers.CharField())


class CreateUserSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=10, trim_whitespace=False)
    is_system_account = serializers.BooleanField(default=False)


class RoleSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    description = serializers.CharField(allow_blank=True)
    is_system_role = serializers.BooleanField()
    permission_codes = serializers.ListField(child=serializers.CharField())


class CreateRoleSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=50)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    permission_codes = serializers.ListField(child=serializers.CharField(), required=False, default=list)


class AssignRoleSerializer(serializers.Serializer):
    role_id = serializers.UUIDField()


class RequestPasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ConfirmPasswordResetSerializer(serializers.Serializer):
    token = serializers.CharField()
    new_password = serializers.CharField(min_length=10, trim_whitespace=False)


# RequestTelegramLinkSerializer/VerifyTelegramLinkSerializer/
# TelegramLinkStatusSerializer (Phase 7) moved to
# apps/employees/interface/serializers.py — Telegram linking is exclusively
# an Employee concern now, never authenticated through Identity's User model.
