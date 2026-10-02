from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models


class Sector(models.Model):
    name = models.CharField(max_length=100, unique=True)
    district = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class WashingStation(models.Model):
    name = models.CharField(max_length=100, unique=True)
    sector = models.ForeignKey(Sector, on_delete=models.PROTECT, related_name="stations")

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


phone_validator = RegexValidator(
    r"^\+?\d{9,15}$", "Phone must be 9-15 digits, optionally starting with '+'."
)


class Farmer(models.Model):
    full_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=16, unique=True, validators=[phone_validator])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.full_name


class Plot(models.Model):
    class RiskStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        CLEAR = "clear", "Clear"
        FLAGGED = "flagged", "Flagged (recently cleared land)"
        CHECK_FAILED = "check_failed", "Check failed (registry unreachable)"

    farmer = models.ForeignKey(Farmer, on_delete=models.PROTECT, related_name="plots")
    name = models.CharField(max_length=100)
    sector = models.ForeignKey(Sector, on_delete=models.PROTECT, related_name="plots")
    washing_station = models.ForeignKey(
        WashingStation, on_delete=models.PROTECT, related_name="plots"
    )
    area_hectares = models.DecimalField(
        max_digits=7, decimal_places=3, validators=[MinValueValidator(Decimal('0.001'))]
    )
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        validators=[MinValueValidator(Decimal('-90')), MaxValueValidator(Decimal('90'))],
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        validators=[MinValueValidator(Decimal('-180')), MaxValueValidator(Decimal('180'))],
    )
    risk_status = models.CharField(
        max_length=16, choices=RiskStatus.choices, default=RiskStatus.PENDING, db_index=True
    )
    risk_checked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(fields=["farmer", "name"], name="unique_plot_name_per_farmer")
        ]

    def __str__(self):
        return f"{self.name} ({self.farmer})"


class RiskCheckAttempt(models.Model):
    class Outcome(models.TextChoices):
        CLEAR = "clear", "Clear"
        FLAGGED = "flagged", "Flagged"
        ERROR = "error", "Error"

    plot = models.ForeignKey(Plot, on_delete=models.CASCADE, related_name="risk_attempts")
    attempt = models.PositiveSmallIntegerField(help_text="1-based, within one check round")
    outcome = models.CharField(max_length=8, choices=Outcome.choices)
    detail = models.CharField(max_length=255, blank=True)
    duration_ms = models.PositiveIntegerField(default=0)
    attempted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]


class Delivery(models.Model):
    class Grade(models.TextChoices):
        A = "A", "Grade A"
        B = "B", "Grade B"
        C = "C", "Grade C"

    plot = models.ForeignKey(Plot, on_delete=models.PROTECT, related_name="deliveries")
    washing_station = models.ForeignKey(
        WashingStation, on_delete=models.PROTECT, related_name="deliveries"
    )
    weight_kg = models.DecimalField(
        max_digits=8, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.1')), MaxValueValidator(Decimal('5000'))],
    )
    grade = models.CharField(max_length=1, choices=Grade.choices)
    delivered_at = models.DateTimeField()
    recorded_at = models.DateTimeField(auto_now_add=True)
    plot_risk_status = models.CharField(max_length=16, choices=Plot.RiskStatus.choices)
    client_ref = models.CharField(max_length=64, unique=True, null=True, blank=True)

    class Meta:
        ordering = ["-id"]
        indexes = [models.Index(fields=["washing_station", "-id"])]

    @property
    def provenance_verified(self):
        return self.plot_risk_status == Plot.RiskStatus.CLEAR


class PriceSchedule(models.Model):
    season = models.CharField(max_length=20)
    grade = models.CharField(max_length=1, choices=Delivery.Grade.choices)
    price_per_kg = models.DecimalField(max_digits=8, decimal_places=2)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["grade"]
        constraints = [
            models.UniqueConstraint(fields=["season", "grade"], name="unique_price_per_season_grade")
        ]