from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models


class Sector(models.Model):
    """Administratuve sector. This F2 enforces it even though F1 scoped against it."""
    
    name = models.CharField(max_length=100, unique=True)
    district = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def centroid(self):
        agg = self.plots.filter(latitude__isnull=False, longitude__isnull=False).aggregate(
            lat=models.Avg("latitude"), lng=models.Avg("longitude")
        )
        return agg["lat"], agg["lng"]


class WashingStation(models.Model):
    """Where cherry is delivered. Formative 2 scopes access against this too."""

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
    # Personal data under Rwanda's Law No. 058/2021 - never serialized in full;
    # see DECISION_LOG.md and FarmerSerializer for who sees what.
    national_id = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.full_name

    @property
    def national_id_masked(self):
        if not self.national_id:
            return ""
        return f"{'*' * max(len(self.national_id) - 4, 0)}{self.national_id[-4:]}"


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
    """One row per call to the external registry: the evidence trail."""

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
    # Copied from the plot at record time so the feed never needs a join to filter by station,
    # and so history survives a plot being moved to another station later.
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
    # Snapshot of the plot's risk status at delivery time (provenance audit trail).
    plot_risk_status = models.CharField(max_length=16, choices=Plot.RiskStatus.choices)
    # Client-generated key so a retry over 2G cannot double-record a delivery.
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


class UserProfile(models.Model):
    """Carries the one thing Django's User model doesn't: a Kawa role.

    A field_agent is also scoped to exactly one washing_station - that's a
    data-scoping fact, not a permission, so it lives here rather than in a
    permission class. See DECISION_LOG.md "enforcement model".
    """

    class Role(models.TextChoices):
        FIELD_AGENT = "field_agent", "Field agent"
        EXPORTER_PARTNER = "exporter_partner", "Exporter partner"
        COMPLIANCE_AUDITOR = "compliance_auditor", "Compliance auditor"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=24, choices=Role.choices)
    washing_station = models.ForeignKey(
        WashingStation, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="field_agents",
        help_text="Required for field_agent; the station this agent is scoped to.",
    )

    def __str__(self):
        return f"{self.user.username} ({self.role})"


class AccessLogEntry(models.Model):
    """Audit trail for Task 4: who looked at a precise location or a farmer's
    identity data, and when - never the value itself.

    Solange's three questions map directly onto this table: 'who can see
    exact coordinates' is answered by RBAC_MATRIX.md; 'who HAS looked at
    identity data this season' and 'what precision left the system' are
    answered by querying this table.
    """

    class Action(models.TextChoices):
        VIEW_PLOT_COORDINATES = "view_plot_coordinates", "Viewed plot coordinates"
        VIEW_FARMER_IDENTITY = "view_farmer_identity", "Viewed farmer identity data"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="access_log")
    role = models.CharField(max_length=24, help_text="Role at the time of access (roles can change later).")
    action = models.CharField(max_length=32, choices=Action.choices)
    # What precision was actually disclosed, not the value - "full" / "coarsened_sector" / "masked" / "none".
    precision = models.CharField(max_length=20)
    object_type = models.CharField(max_length=20)  # "plot" or "farmer"
    object_id = models.PositiveIntegerField()
    sector = models.ForeignKey(Sector, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]
        indexes = [models.Index(fields=["user", "-id"]), models.Index(fields=["action", "-id"])]