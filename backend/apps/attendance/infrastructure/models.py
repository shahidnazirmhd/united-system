"""Django ORM model for Attendance's Holiday entity."""
from __future__ import annotations

from django.db import models

from shared_kernel.infrastructure.base_models import BaseModel


class HolidayRecord(BaseModel):
    name = models.CharField(max_length=150)
    holiday_date = models.DateField(unique=True)
    description = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "attendance_holidays"
        indexes = [
            models.Index(fields=["holiday_date"], name="attendance_holidays_date_idx"),
        ]
        ordering = ["holiday_date"]

    def __str__(self) -> str:
        return f"{self.name} ({self.holiday_date})"
