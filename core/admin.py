from django.contrib import admin

from .models import Delivery, Farmer, Plot, PriceSchedule, RiskCheckAttempt, Sector, WashingStation

for model in (Sector, WashingStation, Farmer, Plot, RiskCheckAttempt, Delivery, PriceSchedule):
    admin.site.register(model)