from datetime import datetime, time as dt_time, timedelta

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
        fields = ["id", "full_name", "member_number", "cooperative", "phone", "national_id", "created_at"]
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
    """`plot_code` stands as the external name for the model's `name` field (found in the F1 Contract).
    while `sector`/`washing_station` is accepted and returned as plain name strings
    (Key thing is that the F1/F2 Contracts sent them this way in this work) - resolved to real FK rows in create()."""

    plot_code = serializers.CharField(source="name")
    sector = serializers.CharField()
    washing_station = serializers.CharField()

    class Meta:
        model = Plot
        fields = ["id", "farmer", "plot_code", "sector", "washing_station", "area_hectares",
                   "latitude", "longitude", "risk_status", "risk_checked_at", "created_at"]
        read_only_fields = ["risk_status", "risk_checked_at", "created_at"]
        validators = []

    def validate(self, attrs):
        lat, lng = attrs.get("latitude"), attrs.get("longitude")
        if (lat is None) != (lng is None):
            raise serializers.ValidationError("Provide both latitude and longitude, or neither.")
        farmer, name = attrs.get("farmer"), attrs.get("name")
        if farmer and name and Plot.objects.filter(farmer=farmer, name=name).exists():
            raise serializers.ValidationError({"plot_code": "This code already exists for this farmer."})
        return attrs

    def create(self, validated_data):
        sector_name = validated_data.pop("sector")
        station_name = validated_data.pop("washing_station")
        sector, _ = Sector.objects.get_or_create(name=sector_name)
        # Inase, the station already exists under a different sector, we keep its
        # prior sector rather than silently moving it - see DECISION_LOG.md.
        station, _ = WashingStation.objects.get_or_create(name=station_name, defaults={"sector": sector})
        return Plot.objects.create(sector=sector, washing_station=station, **validated_data)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["sector"] = instance.sector.name
        data["washing_station"] = instance.washing_station.name
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
    """This serializer accepts either `delivered_at` (full datetime) or `delivered_on` (a bare
    date - as instructed in the F1 Contract); either one given, the stored value is
    always delivered_at. `washing_station` will always be got from the plot, and 
    never from client input, but IS returned (as the station's name) because F2's scoping checks read it. `farmer` and `sector` are also returned, but not accepted,
    because F2's scoping checks read it."""

    farmer = serializers.IntegerField(source="plot.farmer_id", read_only=True)
    sector = serializers.IntegerField(source="plot.sector_id", read_only=True)
    washing_station = serializers.CharField(source="washing_station.name", read_only=True)
    provenance_verified = serializers.BooleanField(read_only=True)
    delivered_on = serializers.DateField(required=False, write_only=True)

    class Meta:
        model = Delivery
        fields = ["id", "plot", "farmer", "sector", "washing_station", "weight_kg", "grade",
                   "delivered_at", "delivered_on", "recorded_at", "plot_risk_status",
                   "provenance_verified", "client_ref"]
        read_only_fields = ["recorded_at", "plot_risk_status"]
        extra_kwargs = {"delivered_at": {"required": False}}

    def validate_delivered_at(self, value):
        if value > timezone.now() + timedelta(minutes=5):
            raise serializers.ValidationError("delivered_at cannot be in the future.")
        return value

    def validate_plot(self, plot):
        if plot.risk_status == Plot.RiskStatus.FLAGGED:
            raise PlotFlagged()
        return plot

    def validate(self, attrs):
        delivered_on = attrs.pop("delivered_on", None)
        if "delivered_at" not in attrs and delivered_on is not None:
            naive = datetime.combine(delivered_on, dt_time.min)
            attrs["delivered_at"] = timezone.make_aware(naive) if timezone.is_naive(naive) else naive
        return attrs

    def create(self, validated_data):
        plot = validated_data["plot"]
        validated_data.setdefault("delivered_at", timezone.now())
        validated_data["washing_station"] = plot.washing_station
        validated_data["plot_risk_status"] = plot.risk_status
        return super().create(validated_data)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        role = get_role(getattr(request, "user", None)) if request else None
        rule = ROLE_RULES.get(role)
        if rule and rule["delivery_fields"] == "metadata_only":
            for field in COMMERCIAL_DELIVERY_FIELDS:
                data.pop(field, None)
        return data

class DeliveryFeedSerializer(serializers.ModelSerializer):
    """This is a compact row for the station feed: only what a phone on 2G needs to render a line."""

    farmer_name = serializers.CharField(source="plot.farmer.full_name", read_only=True)
    plot_name = serializers.CharField(source="plot.name", read_only=True)
    washing_station = serializers.CharField(source="washing_station.name", read_only=True)
    verified = serializers.BooleanField(source="provenance_verified", read_only=True)

    class Meta:
        model = Delivery
        fields = ["id", "farmer_name", "plot_name","washing_station", "weight_kg", "grade", "delivered_at", "verified"]

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