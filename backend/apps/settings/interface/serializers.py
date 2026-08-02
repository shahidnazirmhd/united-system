"""DRF serializers for Settings. Pure protocol translation, no business
validation — matching every other module's interface/serializers.py."""
from __future__ import annotations

from rest_framework import serializers


class SettingResponseSerializer(serializers.Serializer):
    key = serializers.CharField()
    value = serializers.JSONField()
    description = serializers.CharField()


class UpdateSettingSerializer(serializers.Serializer):
    value = serializers.JSONField()
