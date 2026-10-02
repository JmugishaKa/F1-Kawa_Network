from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

from .exceptions import PlotFlagged
from .models import Delivery, Farmer, Plot, PriceSchedule, RiskCheckAttempt, Sector, WashingStation


class SectorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sector
        fields = ["id", "name", "district"]


class WashingStationSerializer(serializers.ModelSerializer):
    class Meta:
        model = WashingStation
        fields = ["id", "name", "sector"]


class FarmerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Farmer
        fields = ["id", "full_name", "phone", "created_at"]
        read_only_fields = ["created_at"]

    def validate_full_name(self, value):
        value = value.strip()
        if len(value) < 2:
            raise serializers.ValidationError("Name is too short.")
        return value


class PlotSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plot
        fields = [
            "id", "farmer", "name", "sector", "washing_station", "area_hectares",
            "latitude", "longitude", "risk_status", "risk_checked_at", "created_at",
        ]
        read_only_fields = ["risk_status", "risk_checked_at", "created_at"]
        validators = []

    def validate(self, attrs):
    # only one of lat/lng doesn't make sense as a coordinate, so reject that combo
        lat, lng = attrs.get("latitude"), attrs.get("longitude")
        if (lat is None) != (lng is None):
            raise serializers.ValidationError("Provide both latitude and longitude, or neither.")
        farmer, name = attrs.get("farmer"), attrs.get("name")
        if farmer and name and Plot.objects.filter(farmer=farmer, name=name).exists():
            raise serializers.ValidationError({"name": "This farmer already has a plot with that name."})
        return attrs


class RiskCheckAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = RiskCheckAttempt
        fields = ["id", "attempt", "outcome", "detail", "duration_ms", "attempted_at"]


class DeliverySerializer(serializers.ModelSerializer):
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
# blocking flagged plots here (not in the view) so it comes back as a normal
# structured validation-style error instead of some generic 500
        if plot.risk_status == Plot.RiskStatus.FLAGGED:
            raise PlotFlagged()
        return plot

    def create(self, validated_data):
        plot = validated_data["plot"]
        validated_data.setdefault("delivered_at", timezone.now())
        validated_data["washing_station"] = plot.washing_station
        validated_data["plot_risk_status"] = plot.risk_status
        return super().create(validated_data)


class DeliveryFeedSerializer(serializers.ModelSerializer):
    farmer_name = serializers.CharField(source="plot.farmer.full_name", read_only=True)
    plot_name = serializers.CharField(source="plot.name", read_only=True)
    verified = serializers.BooleanField(source="provenance_verified", read_only=True)

    class Meta:
        model = Delivery
        fields = ["id", "farmer_name", "plot_name", "weight_kg", "grade", "delivered_at", "verified"]


class PriceSerializer(serializers.ModelSerializer):
    class Meta:
        model = PriceSchedule
        fields = ["grade", "price_per_kg"]