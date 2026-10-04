from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

from .exceptions import PlotFlagged
from .models import AccessLogEntry, Delivery, Farmer, Plot, PriceSchedule, RiskCheckAttempt, Sector, WashingStation
from .rbac import COMMERCIAL_DELIVERY_FIELDS, ROLE_RULES, get_role


def _log_access(request, action, precision, object_type, object_id, sector_id=None):
    """Record that a role saw a location/identity field, without storing the value itself."""
    if request is None or not getattr(request.user, "is_authenticated", False):
        return
    AccessLogEntry.objects.create(
        user=request.user, role=get_role(request.user) or "", action=action,
        precision=precision, object_type=object_type, object_id=object_id, sector_id=sector_id,
    )


class SectorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sector
        fields = ["id", "name", "district"]


class WashingStationSerializer(serializers.ModelSerializer):
    class Meta:
        model = WashingStation
        fields = ["id", "name", "sector"]


class FarmerSerializer(serializers.ModelSerializer):
    national_id = serializers.SerializerMethodField()

    class Meta:
        model = Farmer
        fields = ["id", "full_name", "phone", "national_id", "created_at"]
        read_only_fields = ["created_at"]

    def validate_full_name(self, value):
        value = value.strip()
        if len(value) < 2:
            raise serializers.ValidationError("Name is too short.")
        return value

    def get_national_id(self, farmer):
        """Masked for field_agent, absent (None, then stripped below) for everyone else."""
        request = self.context.get("request")
        role = get_role(getattr(request, "user", None)) if request else None
        rule = ROLE_RULES.get(role)
        if rule is None or rule["national_id"] == "absent":
            return None
        value = farmer.national_id_masked
        _log_access(request, AccessLogEntry.Action.VIEW_FARMER_IDENTITY, "masked", "farmer", farmer.pk)
        return value

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # "not present" in the matrix means the key itself is gone, not null.
        if data.get("national_id") is None:
            data.pop("national_id", None)
        return data


class PlotSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plot
        fields = [
            "id", "farmer", "name", "sector", "washing_station", "area_hectares",
            "latitude", "longitude", "risk_status", "risk_checked_at", "created_at",
        ]
        read_only_fields = ["risk_status", "risk_checked_at", "created_at"]
        # Replace the auto UniqueTogether error with a clearer one (see validate()).
        validators = []

    def validate(self, attrs):
        lat, lng = attrs.get("latitude"), attrs.get("longitude")
        if (lat is None) != (lng is None):
            raise serializers.ValidationError("Provide both latitude and longitude, or neither.")
        farmer, name = attrs.get("farmer"), attrs.get("name")
        if farmer and name and Plot.objects.filter(farmer=farmer, name=name).exists():
            raise serializers.ValidationError({"name": "This farmer already has a plot with that name."})
        return attrs

    def to_representation(self, instance):
        """Role-aware coordinates. F2: field_agent/auditor see the real point,
        exporter_partner sees the sector's derived centroid (see Sector.centroid)."""
        data = super().to_representation(instance)
        request = self.context.get("request")
        role = get_role(getattr(request, "user", None)) if request else None
        rule = ROLE_RULES.get(role)
        if rule is None:
            data["latitude"] = data["longitude"] = None
            return data
        if rule["coordinate_precision"] == "coarsened_sector":
            lat, lng = instance.sector.centroid()
            data["latitude"], data["longitude"] = lat, lng
            _log_access(request, AccessLogEntry.Action.VIEW_PLOT_COORDINATES, "coarsened_sector",
                        "plot", instance.pk, sector_id=instance.sector_id)
        elif instance.latitude is not None:
            _log_access(request, AccessLogEntry.Action.VIEW_PLOT_COORDINATES, "full",
                        "plot", instance.pk, sector_id=instance.sector_id)
        return data


class RiskCheckAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = RiskCheckAttempt
        fields = ["id", "attempt", "outcome", "detail", "duration_ms", "attempted_at"]


class DeliverySerializer(serializers.ModelSerializer):
    """Full record: used to create a delivery and to read one back."""

    farmer = serializers.IntegerField(source="plot.farmer_id", read_only=True)
    sector = serializers.IntegerField(source="plot.sector_id", read_only=True)
    provenance_verified = serializers.BooleanField(read_only=True)

    class Meta:
        model = Delivery
        fields = [
            "id", "plot", "farmer", "sector", "washing_station", "weight_kg", "grade",
            "delivered_at", "recorded_at", "plot_risk_status", "provenance_verified", "client_ref",
        ]
        read_only_fields = ["washing_station", "recorded_at", "plot_risk_status"]
        extra_kwargs = {"delivered_at": {"required": False}}

    def validate_delivered_at(self, value):
        if value > timezone.now() + timedelta(minutes=5):
            raise serializers.ValidationError("delivered_at cannot be in the future.")
        return value

    def validate_plot(self, plot):
        if plot.risk_status == Plot.RiskStatus.FLAGGED:
            raise PlotFlagged()
        return plot

    def create(self, validated_data):
        plot = validated_data["plot"]
        validated_data.setdefault("delivered_at", timezone.now())
        validated_data["washing_station"] = plot.washing_station
        validated_data["plot_risk_status"] = plot.risk_status
        return super().create(validated_data)

    def to_representation(self, instance):
        """compliance_auditor gets metadata only: price-relevant fields are
        stripped, not just hidden by permission - a 403 on the whole object
        would be wrong, since the auditor IS allowed to see the delivery exists."""
        data = super().to_representation(instance)
        request = self.context.get("request")
        role = get_role(getattr(request, "user", None)) if request else None
        rule = ROLE_RULES.get(role)
        if rule and rule["delivery_fields"] == "metadata_only":
            for field in COMMERCIAL_DELIVERY_FIELDS:
                data.pop(field, None)
        return data


class DeliveryFeedSerializer(serializers.ModelSerializer):
    """Compact row for the station feed: only what a phone on 2G needs to render a line."""

    farmer_name = serializers.CharField(source="plot.farmer.full_name", read_only=True)
    plot_name = serializers.CharField(source="plot.name", read_only=True)
    verified = serializers.BooleanField(source="provenance_verified", read_only=True)

    class Meta:
        model = Delivery
        fields = ["id", "farmer_name", "plot_name", "weight_kg", "grade", "delivered_at", "verified"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        role = get_role(getattr(request, "user", None)) if request else None
        rule = ROLE_RULES.get(role)
        if rule and rule["delivery_fields"] == "metadata_only":
            for field in COMMERCIAL_DELIVERY_FIELDS:
                data.pop(field, None)
        return data


class PriceSerializer(serializers.ModelSerializer):
    class Meta:
        model = PriceSchedule
        fields = ["grade", "price_per_kg"]


class AccessLogEntrySerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True, default=None)

    class Meta:
        model = AccessLogEntry
        fields = [
            "id", "username", "role", "action", "precision", "object_type",
            "object_id", "sector", "created_at",
        ]