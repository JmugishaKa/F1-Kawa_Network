from django.contrib import admin

from .models import (
    AccessLogEntry, Delivery, Farmer, Plot, PriceSchedule, RiskCheckAttempt,
    Sector, UserProfile, WashingStation,
)

for model in (
    Sector, WashingStation, Farmer, Plot, RiskCheckAttempt, Delivery, PriceSchedule,
    UserProfile, AccessLogEntry,
):
    admin.site.register(model)