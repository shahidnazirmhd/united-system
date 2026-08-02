"""DRF serializers for Attendance. Pure protocol translation, no business
validation — matching every other module's interface/serializers.py."""
from __future__ import annotations

from rest_framework import serializers


class CreateHolidaySerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    holiday_date = serializers.DateField()
    description = serializers.CharField(required=False, allow_blank=True, default="")


class UpdateHolidaySerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    holiday_date = serializers.DateField()
    description = serializers.CharField(required=False, allow_blank=True, default="")
    is_active = serializers.BooleanField(default=True)


class HolidayResponseSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    holiday_date = serializers.DateField()
    description = serializers.CharField(allow_blank=True)
    is_active = serializers.BooleanField()
